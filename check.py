from app import app, db
from models import Project, HedgeRecommendation, MarketView

with app.app_context():
    h = HedgeRecommendation.query.all()
    for hedge in h:
        print(f"Material: {hedge.material_name}, Ticker: {hedge.ticker}")
        print(f"Base Hedge: {hedge.base_recommended_amount}, Alpha-adjusted: {hedge.recommended_amount}")
        print("-" * 30)

    v = MarketView.query.all()
    for view in v:
        print(f"View on: {view.material_name}, Prediction: {view.prediction_pct}, Confidence: {view.confidence_level}")
