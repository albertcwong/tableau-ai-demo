"""Tests for Tableau metadata cache models."""
from datetime import datetime, timedelta
from app.models.tableau import Datasource, View


def test_datasource_cache(db_session):
    """Test caching a datasource."""
    ds = Datasource(
        tableau_id="ds-123",
        name="Sales Data",
        project="Finance"
    )
    db_session.add(ds)
    db_session.commit()
    
    retrieved = db_session.query(Datasource).filter_by(tableau_id="ds-123").first()
    assert retrieved is not None
    assert retrieved.name == "Sales Data"
    assert retrieved.project == "Finance"


def test_view_datasource_relationship(db_session):
    """Test view-datasource relationship."""
    ds = Datasource(
        tableau_id="ds-123",
        name="Sales Data",
        project="Finance"
    )
    db_session.add(ds)
    db_session.commit()
    
    view = View(
        tableau_id="v-456",
        name="Sales Dashboard",
        workbook="Sales Workbook",
        datasource_id=ds.id
    )
    db_session.add(view)
    db_session.commit()
    
    assert view.datasource.tableau_id == "ds-123"
    assert len(ds.views) == 1
    assert ds.views[0].name == "Sales Dashboard"


def test_datasource_unique_tableau_id(db_session):
    """Test that tableau_id must be unique."""
    ds1 = Datasource(tableau_id="ds-123", name="First")
    ds2 = Datasource(tableau_id="ds-123", name="Second")
    
    db_session.add(ds1)
    db_session.commit()
    
    db_session.add(ds2)
    try:
        db_session.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        db_session.rollback()


def test_view_unique_tableau_id(db_session):
    """Test that view tableau_id must be unique."""
    view1 = View(tableau_id="v-123", name="First")
    view2 = View(tableau_id="v-123", name="Second")
    
    db_session.add(view1)
    db_session.commit()
    
    db_session.add(view2)
    try:
        db_session.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        db_session.rollback()


def test_datasource_cascade_delete(db_session):
    """Test that deleting datasource deletes views."""
    ds = Datasource(tableau_id="ds-123", name="Sales Data")
    db_session.add(ds)
    db_session.commit()
    
    view1 = View(tableau_id="v-1", name="View 1", datasource_id=ds.id)
    view2 = View(tableau_id="v-2", name="View 2", datasource_id=ds.id)
    db_session.add_all([view1, view2])
    db_session.commit()
    
    ds_id = ds.id
    db_session.delete(ds)
    db_session.commit()
    
    # Verify views are deleted
    remaining_views = db_session.query(View).filter_by(datasource_id=ds_id).all()
    assert len(remaining_views) == 0


def test_datasource_updated_at(db_session):
    """Test that updated_at changes on modification."""
    ds = Datasource(tableau_id="ds-123", name="Sales Data")
    db_session.add(ds)
    db_session.commit()
    
    original_updated = ds.updated_at
    
    # Update datasource
    ds.name = "Updated Sales Data"
    db_session.commit()
    
    # updated_at should be updated
    assert ds.updated_at > original_updated


def test_view_without_datasource(db_session):
    """Test that view can exist without datasource."""
    view = View(
        tableau_id="v-123",
        name="Standalone View",
        workbook="My Workbook"
    )
    db_session.add(view)
    db_session.commit()
    
    assert view.id is not None
    assert view.datasource_id is None
    assert view.datasource is None
