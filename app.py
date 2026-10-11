from flask import Flask, flash, render_template, request, redirect, url_for, jsonify
from sqlalchemy import inspect, text
from config import Config
from models import db, Project, Material, HedgeRecommendation, MarketView
from engine.mce import MaterialCorrelationEngine
from engine.gis_analyzer import GISAnalyzer
from engine.backtester import RiskManager, BacktesterEngine
from engine.intelligence import InsightEngine
from engine.black_litterman import BlackLittermanEngine
from engine.geopolitical import GeopoliticalEngine
from engine.sustainability import SustainabilityEngine
from engine.mce import MaterialCorrelationEngine
from datetime import datetime
import os
import numpy as np

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def ensure_schema():
    db.create_all()
    inspector = inspect(db.engine)
    table_column_types = {
        'project': {
            'id': 'INTEGER', 'name': 'VARCHAR(100)', 'description': 'TEXT', 'created_at': 'DATETIME',
            'location_name': 'VARCHAR(100)', 'lat': 'FLOAT', 'lon': 'FLOAT', 'agglomeration_score': 'FLOAT',
            'mean_cost': 'FLOAT', 'var_95': 'FLOAT', 'sim_timestamp': 'DATETIME',
            'total_carbon_offset': 'FLOAT', 'sustainability_premium': 'FLOAT', 'backtest_sharpe': 'FLOAT',
            'backtest_vol_reduction': 'FLOAT', 'backtest_max_drawdown': 'FLOAT'
        },
        'material': {
            'id': 'INTEGER', 'project_id': 'INTEGER', 'name': 'VARCHAR(50)', 'quantity': 'FLOAT',
            'unit': 'VARCHAR(20)', 'estimated_cost': 'FLOAT', 'is_upcycled': 'BOOLEAN', 'carbon_footprint': 'FLOAT'
        },
        'market_view': {
            'id': 'INTEGER', 'project_id': 'INTEGER', 'material_name': 'VARCHAR(50)', 'prediction_pct': 'FLOAT',
            'confidence_level': 'INTEGER', 'is_news_derived': 'BOOLEAN', 'timestamp': 'DATETIME'
        },
        'hedge_recommendation': {
            'id': 'INTEGER', 'project_id': 'INTEGER', 'material_name': 'VARCHAR(50)', 'ticker': 'VARCHAR(10)',
            'correlation': 'FLOAT', 'recommended_amount': 'FLOAT', 'base_recommended_amount': 'FLOAT',
            'confidence_score': 'FLOAT', 'is_johansen': 'BOOLEAN', 'mean_reversion_speed': 'FLOAT', 'timestamp': 'DATETIME'
        }
    }

    for table_name, columns in table_column_types.items():
        if not inspector.has_table(table_name):
            continue
        existing = {col['name'] for col in inspector.get_columns(table_name)}
        for column_name, column_type in columns.items():
            if column_name in existing:
                continue
            with db.engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))


with app.app_context():
    ensure_schema()

mce = MaterialCorrelationEngine(Config)
gis = GISAnalyzer()
rm = RiskManager(Config)
ie = InsightEngine()
bl = BlackLittermanEngine()
geo_engine = GeopoliticalEngine()
sus_engine = SustainabilityEngine()
bt_engine = BacktesterEngine(Config)

@app.before_request
def create_tables():
    db.create_all()

    inspector = inspect(db.engine)
    existing = set(inspector.get_table_names())

    if 'project' in existing:
        project_cols = {col['name'] for col in inspector.get_columns('project')}
        expected = {
            'id', 'name', 'description', 'created_at', 'location_name', 'lat', 'lon',
            'agglomeration_score', 'mean_cost', 'var_95', 'sim_timestamp',
            'total_carbon_offset', 'sustainability_premium', 'backtest_sharpe',
            'backtest_vol_reduction', 'backtest_max_drawdown'
        }
        missing = expected - project_cols
        if missing:
            with db.engine.begin() as conn:
                for col in sorted(missing):
                    conn.execute(text(f'ALTER TABLE project ADD COLUMN {col} FLOAT'))

    if 'hedge_recommendation' in existing:
        hedge_cols = {col['name'] for col in inspector.get_columns('hedge_recommendation')}
        expected = {
            'id', 'project_id', 'material_name', 'ticker', 'correlation',
            'recommended_amount', 'base_recommended_amount', 'confidence_score',
            'is_johansen', 'mean_reversion_speed', 'timestamp'
        }
        missing = expected - hedge_cols
        if missing:
            with db.engine.begin() as conn:
                for col in sorted(missing):
                    if col in {'confidence_score', 'is_johansen', 'mean_reversion_speed'}:
                        conn.execute(text(f'ALTER TABLE hedge_recommendation ADD COLUMN {col} FLOAT'))
                    elif col == 'timestamp':
                        conn.execute(text(f'ALTER TABLE hedge_recommendation ADD COLUMN {col} DATETIME'))
                    else:
                        conn.execute(text(f'ALTER TABLE hedge_recommendation ADD COLUMN {col} FLOAT'))

    if 'market_view' in existing:
        view_cols = {col['name'] for col in inspector.get_columns('market_view')}
        expected = {'id', 'project_id', 'material_name', 'prediction_pct', 'confidence_level', 'is_news_derived', 'timestamp'}
        missing = expected - view_cols
        if missing:
            with db.engine.begin() as conn:
                for col in sorted(missing):
                    if col in {'prediction_pct', 'confidence_level'}:
                        conn.execute(text(f'ALTER TABLE market_view ADD COLUMN {col} FLOAT'))
                    elif col == 'timestamp':
                        conn.execute(text(f'ALTER TABLE market_view ADD COLUMN {col} DATETIME'))
                    elif col == 'is_news_derived':
                        conn.execute(text(f'ALTER TABLE market_view ADD COLUMN {col} BOOLEAN'))
                    else:
                        conn.execute(text(f'ALTER TABLE market_view ADD COLUMN {col} FLOAT'))

    if 'material' in existing:
        material_cols = {col['name'] for col in inspector.get_columns('material')}
        expected = {'id', 'project_id', 'name', 'quantity', 'unit', 'estimated_cost', 'is_upcycled', 'carbon_footprint'}
        missing = expected - material_cols
        if missing:
            with db.engine.begin() as conn:
                for col in sorted(missing):
                    if col == 'is_upcycled':
                        conn.execute(text('ALTER TABLE material ADD COLUMN is_upcycled BOOLEAN'))
                    elif col == 'carbon_footprint':
                        conn.execute(text('ALTER TABLE material ADD COLUMN carbon_footprint FLOAT'))
                    else:
                        conn.execute(text(f'ALTER TABLE material ADD COLUMN {col} FLOAT'))

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/dashboard')
def index():
    projects = Project.query.all()
    total_materials = sum(len(project.materials) for project in projects)
    total_hedges = sum(len(project.hedge_recommendations) for project in projects)
    return render_template(
        'dashboard.html',
        projects=projects,
        total_materials=total_materials,
        total_hedges=total_hedges,
    )

@app.route('/project/add', methods=['POST'])
def add_project():
    name = request.form.get('name')
    description = request.form.get('description')
    location_name = request.form.get('location_name', 'Unknown')
    lat = float(request.form.get('lat', 0) or 0)
    lon = float(request.form.get('lon', 0) or 0)
    
    if name:
        new_project = Project(
            name=name, 
            description=description,
            location_name=location_name,
            lat=lat,
            lon=lon
        )
        db.session.add(new_project)
        db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/project/<int:project_id>')
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Generate insights on the fly
    sim_data = {
        'mean_cost': project.mean_cost or 0,
        'var_95': project.var_95 or 0
    }
    insights = ie.get_pivot_suggestions(project, sim_data)
    
    # Aggregate ESG Data
    total_footprint = 0
    total_offset = 0
    upcycled_count = 0
    for m in project.materials:
        res = sus_engine.calculate_esv(m)
        total_footprint += res.get('footprint', res.get('footprint_kg', 0))
        total_offset += res.get('offset', res.get('offset_kg', 0))
        if m.is_upcycled:
            upcycled_count += 1
            
    project.total_carbon_offset = total_offset / 1000.0 # Convert to Tons
    if project.materials:
        project.sustainability_premium = (upcycled_count / len(project.materials)) * 12.0 # Max 12% premium
    
    db.session.commit()
    
    return render_template('project_detail.html', project=project, insights=insights, total_footprint=total_footprint)


@app.route('/project/<int:project_id>/simulate')
def run_simulation(project_id):
    project = Project.query.get_or_404(project_id)
    materials = [
        {'name': m.name, 'exposure': m.estimated_cost or 0} 
        for m in project.materials
    ]
    
    if materials:
        results = rm.run_monte_carlo(materials)
        project.mean_cost = results['mean_cost']
        project.var_95 = results['var_95']
        project.sim_timestamp = datetime.utcnow()
        db.session.commit()
        
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/project/<int:project_id>/agglomeration/calculate')
def calculate_agglomeration(project_id):
    project = Project.query.get_or_404(project_id)
    if project.lat and project.lon:
        res = gis.get_agglomeration_score(project.lat, project.lon)
        if res:
            project.agglomeration_score = res['score']
            db.session.commit()
            
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/project/<int:project_id>/material/add', methods=['POST'])
def add_material(project_id):
    name = request.form.get('name')
    quantity = float(request.form.get('quantity', 0))
    unit = request.form.get('unit')
    estimated_cost = float(request.form.get('estimated_cost', 0))
    is_upcycled = request.form.get('is_upcycled') == 'on'
    
    if name and quantity:
        material = Material(
            project_id=project_id, 
            name=name, 
            quantity=quantity, 
            unit=unit, 
            estimated_cost=estimated_cost,
            is_upcycled=is_upcycled
        )
        # Calculate ESG metrics immediately
        esg_res = sus_engine.calculate_esv(material)
        material.carbon_footprint = esg_res.get('footprint', esg_res.get('footprint_kg', 0))
        
        db.session.add(material)
        db.session.commit()
        
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/project/<int:project_id>/view/add', methods=['POST'])
def add_view(project_id):
    material_name = request.form.get('material_name')
    prediction_pct = float(request.form.get('prediction_pct', 0)) / 100.0
    confidence = int(request.form.get('confidence', 5))
    
    if material_name:
        view = MarketView(
            project_id=project_id,
            material_name=material_name,
            prediction_pct=prediction_pct,
            confidence_level=confidence,
            is_news_derived=False
        )
        db.session.add(view)
        db.session.commit()
    
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/project/<int:project_id>/view/delete/<int:view_id>')
def delete_view(project_id, view_id):
    view = MarketView.query.get_or_404(view_id)
    db.session.delete(view)
    db.session.commit()
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/project/<int:project_id>/hedge/calculate')
def calculate_hedge(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Clear existing recommendations to avoid duplicates
    HedgeRecommendation.query.filter_by(project_id=project_id).delete()
    
    # Check for Black-Litterman Views
    views = []
    view_data = MarketView.query.filter_by(project_id=project_id).all()
    for v in view_data:
        # Get ticker for the material name
        ticker = Config.MATERIAL_TICKERS.get(v.material_name.lower())
        if ticker:
            views.append({
                'ticker': ticker,
                'prediction': v.prediction_pct,
                'confidence': v.confidence_level
            })

    recommendations = []
    
    # Get all tickers in a list for the matrix
    all_tickers = list(Config.MATERIAL_TICKERS.values())
    
    # If we have views, run BL
    adjusted_returns = None
    if views:
        # Get historical correlation matrix (simplify for MVP by fetching from MCE)
        # Note: In a real app we'd cache this or pass it properly
        corr_data, _ = mce.calculate_correlation('copper') # Just to get a matrix structure
        if corr_data:
            tickers = [c['ticker'] for c in corr_data]
            # Mock identity matrix for correlation if we don't have a full matrix
            # Real version would fetch a full pairwise matrix
            matrix = np.eye(len(tickers)) 
            priors = {t: 0.0 for t in tickers} # Market equilibrium is 0 growth
            adjusted_returns = bl.calculate_posterior(tickers, matrix, priors, views)

    for material in project.materials:
        result, error = mce.suggest_hedge(
            material.name, 
            material.estimated_cost or 100,
            adjusted_returns=adjusted_returns
        )
        if result:
            recommendations.append(result)
            # Save to DB
            hedge = HedgeRecommendation(
                project_id=project_id,
                material_name=material.name,
                ticker=result['recommended_ticker'],
                correlation=result['correlation'],
                recommended_amount=result['suggested_hedge_value'],
                base_recommended_amount=result['base_hedge_value'],
                confidence_score=result.get('confidence_score', 0),
                is_johansen=result.get('is_johansen', False),
                mean_reversion_speed=result.get('mean_reversion_speed', 0.0)
            )
            db.session.add(hedge)

    
    db.session.commit()
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/geopolitical', methods=['GET', 'POST'])
def geopolitical_radar():
    results = None
    impacted_projects = []
    graph_data = None
    form_values = {
        'country_a': request.form.get('country_a', ''),
        'country_b': request.form.get('country_b', ''),
        'severity': request.form.get('severity', 'high'),
        'duration_days': request.form.get('duration_days', '30'),
        'event_id': request.form.get('event_id', ''),
    }
    if request.method == 'POST':
        event_id = form_values['event_id']
        if event_id:
            event = geo_engine.knowledge_base['historical_events'].get(event_id)
            if event:
                form_values.update({
                    'country_a': event['country_a'],
                    'country_b': event['country_b'],
                    'severity': event['severity'],
                    'duration_days': str(event['duration_days']),
                })
        country_a = form_values['country_a']
        country_b = form_values['country_b']
        if country_a and country_b:
            try:
                results = geo_engine.simulate_conflict(
                    country_a,
                    country_b,
                    severity=form_values['severity'],
                    duration_days=form_values['duration_days'],
                    event_id=event_id or None,
                )
            except (ValueError, TypeError) as error:
                flash(str(error), 'error')
            if results:
                # The graph is a view of this exact result, not a second simulation.
                graph_data = results['graph_data']
                total_base_cost = 0.0
                total_delta_cost = 0.0
                for project in Project.query.all():
                    impact = geo_engine.calculate_bom_impact(project, results['price_shocks'])
                    if impact['items']:
                        impacted_projects.append({'project': project, **impact})
                        total_base_cost += impact['total_base_cost']
                        total_delta_cost += impact['total_delta_cost']
                results['bom_exposure_pct'] = (
                    total_delta_cost / total_base_cost * 100.0 if total_base_cost else 0.0
                )
                results['flash_commodity'] = next(iter(results['price_shocks'].values()), None)
                if results['flash_commodity']:
                    results['flash_commodity_id'] = next(iter(results['price_shocks']))

    return render_template(
        'geopolitics.html',
        results=results,
        impacted_projects=impacted_projects,
        graph_data=graph_data,
        form_values=form_values,
        severity_options=geo_engine.knowledge_base['severity_multipliers'],
        historical_events=geo_engine.knowledge_base['historical_events'],
    )



@app.route('/project/<int:project_id>/backtest')
def backtest_project(project_id):
    project = Project.query.get_or_404(project_id)
    if not project.materials or not project.hedge_recommendations:
        return jsonify({"error": "Need both materials and hedge recommendations to backtest."}), 400
    
    # Backtest the top material
    mat = project.materials[0]
    hedge = HedgeRecommendation.query.filter_by(project_id=project_id, material_name=mat.name).first()
    
    if not hedge:
        return jsonify({"error": f"No hedge found for {mat.name}"}), 404
        
    m_ticker = Config.MATERIAL_TICKERS.get(mat.name.lower())
    results, error = bt_engine.run_backtest(m_ticker, hedge.ticker)
    
    if error:
        return jsonify({"error": error}), 500
    
    try:
        project.backtest_sharpe = float(results['metrics']['sharpe'])
        project.backtest_vol_reduction = float(results['metrics']['vol_reduction'])
        project.backtest_max_drawdown = float(results['metrics']['max_drawdown'])
        db.session.commit()
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5011))
    app.run(debug=True, port=port)
