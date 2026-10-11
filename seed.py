from app import app, db
from models import Project, Material
from engine.gis_analyzer import GISAnalyzer

with app.app_context():
    # Make sure tables exist
    db.create_all()

    # Create a project
    project = Project(
        name="Test Project",
        description="A project for testing hedging",
        location_name="Seattle, WA",
        lat=47.6062,
        lon=-122.3321
    )
    db.session.add(project)
    db.session.commit()

    # Create materials
    m1 = Material(project_id=project.id, name="copper", quantity=5000, unit="lbs", estimated_cost=10000)
    m2 = Material(project_id=project.id, name="steel", quantity=10000, unit="lbs", estimated_cost=20000)
    db.session.add(m1)
    db.session.add(m2)
    db.session.commit()

    print("Database seeded with a project and materials.")
