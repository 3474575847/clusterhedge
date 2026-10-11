from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    materials = db.relationship('Material', backref='project', lazy=True)
    hedge_recommendations = db.relationship('HedgeRecommendation', backref='project', lazy=True)
    market_views = db.relationship('MarketView', backref='project', lazy=True)
    
    # Phase 2: GIS Spatial Alpha
    location_name = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    agglomeration_score = db.Column(db.Float)
    
    # Phase 3: Simulations & Intelligence
    mean_cost = db.Column(db.Float)
    var_95 = db.Column(db.Float)
    sim_timestamp = db.Column(db.DateTime)
    
    # Phase 4: Institutional Upgrade (ESG & Backtesting)
    total_carbon_offset = db.Column(db.Float, default=0.0) # In metric tons
    sustainability_premium = db.Column(db.Float, default=0.0) # In %
    backtest_sharpe = db.Column(db.Float)
    backtest_vol_reduction = db.Column(db.Float) 
    backtest_max_drawdown = db.Column(db.Float)


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False) # e.g., Copper, Lumber
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False) # kg, ft, etc.
    estimated_cost = db.Column(db.Float)
    
    # ESG Attributes
    is_upcycled = db.Column(db.Boolean, default=False)
    carbon_footprint = db.Column(db.Float, default=0.0) # CO2e per unit

class MarketView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    material_name = db.Column(db.String(50), nullable=False)
    prediction_pct = db.Column(db.Float, nullable=False) # e.g. 0.05 for +5%
    confidence_level = db.Column(db.Integer, default=5) # 1-10
    is_news_derived = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class HedgeRecommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    material_name = db.Column(db.String(50))
    ticker = db.Column(db.String(10))
    correlation = db.Column(db.Float)
    recommended_amount = db.Column(db.Float) # This will be the Alpha-adjusted one
    base_recommended_amount = db.Column(db.Float) # This will be the pure Market one
    confidence_score = db.Column(db.Float)
    is_johansen = db.Column(db.Boolean)
    mean_reversion_speed = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

