"""Tests for stats_fns module."""

import datetime
import zoneinfo
from unittest.mock import MagicMock, Mock

import pytest
from functions import stats_fns
from services import firestore

@pytest.fixture
def mock_firestore(monkeypatch):
    """Mocks firestore client."""
    mock_db = MagicMock()
    monkeypatch.setattr('services.firestore.db', lambda: mock_db)
    return mock_db

def _create_mock_user_doc(user_id, last_login_dt, days_used, viewed):
    doc = MagicMock()
    doc.id = user_id
    doc.exists = True
    
    # Store data to be returned by to_dict()
    data = {
        "client_num_days_used": days_used,
        "client_num_viewed": viewed,
        "last_login_at": last_login_dt
    }
    doc.to_dict.return_value = data
    return doc

def test_joke_stats_calculate(mock_firestore):
    """Test the daily stats calculation."""
    
    # Setup mock data
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now_utc - datetime.timedelta(hours=1)
    two_days_ago = now_utc - datetime.timedelta(days=2)
    six_days_ago = now_utc - datetime.timedelta(days=6)
    eight_days_ago = now_utc - datetime.timedelta(days=8)
    
    # Users for test scenarios:
    # 1. Active yesterday (should be in 1d and 7d stats)
    # 2. Active 6 days ago (should be in 7d stats only)
    # 3. Active 8 days ago (should be in neither)
    # 4. Another active yesterday (to test aggregation)
    
    # Note: The function queries for last_login_at >= 168 hours ago (7 days)
    # We will simulate the query return.
    
    users_data = [
        # User 1: Active 1h ago, 10 days used, 100 views
        ("user1", one_hour_ago, 10, 100),
        # User 2: Active 6d ago, 5 days used, 50 views
        ("user2", six_days_ago, 5, 50),
        # User 3: Active 8d ago - should technically be filtered out by query, 
        # but if returned, we ensure logic handles it (though logic iterates query results)
        # However, to test the query filter itself we'd need integration tests. 
        # Here we mock the query return. The code should apply logic to classify.
        
        # User 4: Active 1h ago, 10 days used, 200 views
        ("user4", one_hour_ago, 10, 200),
    ]
    
    mock_docs = [_create_mock_user_doc(*u) for u in users_data]
    
    # Mock the query stream
    mock_collection = mock_firestore.collection.return_value
    mock_query = mock_collection.where.return_value
    mock_query.stream.return_value = mock_docs
    
    # Mock event
    event = MagicMock()
    
    # Run function
    stats_fns.joke_stats_calculate.__wrapped__(event)
    
    # Verify Firestore writes
    # Expect 1 write to joke_stats collection
    mock_firestore.collection.assert_any_call("joke_stats")
    
    # Get the set call arguments
    # We need to find the specific call to .document().set()
    # mock_firestore.collection("joke_stats").document("YYYYMMDD").set(...)
    
    # Inspect calls to collection("joke_stats")
    joke_stats_collection_calls = [
        c for c in mock_firestore.collection.mock_calls 
        if c.args == ("joke_stats",)
    ]
    assert len(joke_stats_collection_calls) >= 1
    
    # The chain is collection().document().set()
    # We can inspect the mock_firestore object directly if we traverse the chain
    # But it's easier if we assign return values in setup if we want strict checking.
    # Given the concise mock setup, we can check the last set call on the chain.
    
    # Let's inspect what was passed to set()
    # It's hard to get the exact doc ID since it depends on current date execution
    # But we can verify the data structure.
    
    # Access the doc ref returned by collection("joke_stats").document(...)
    # Since we didn't explicitly mock the return of document(), it returns a new MagicMock
    # which we can't easily access from here unless we traverse.
    
    # Traversing:
    stats_doc_ref = mock_firestore.collection("joke_stats").document.return_value
    stats_set_call = stats_doc_ref.set.call_args
    assert stats_set_call is not None
    
    data, = stats_set_call.args
    kwargs = stats_set_call.kwargs
    
    assert kwargs.get("merge") is True
    
    # Verify 1d stats
    # User 1 (10 days) and User 4 (10 days) are active within 24h
    # User 2 (5 days) is not active within 24h (6 days ago)
    # Expected: { "10": 2 }
    # Note: Keys are strings in Firestore maps usually, but Python dicts can have int keys. 
    # Firestore client handles int keys but they are often stored as numbers. 
    # However, for Map keys, Firestore requires strings. 
    # Let's check if the code converts to string or if we should.
    # The requirement says "map from ... to ...". 
    # Usually safer to stringify keys for Firestore maps.
    # Let's see what the implementation does.
    
    num_1d_map = data.get("num_1d_users_by_days_used", {})
    # Assuming code produces string keys:
    assert str(10) in num_1d_map or 10 in num_1d_map
    val_10 = num_1d_map.get(str(10)) or num_1d_map.get(10)
    assert val_10 == 2
    
    assert str(5) not in num_1d_map and 5 not in num_1d_map
    
    # Verify 1d stats by jokes viewed
    # User 1 (100 views) and User 4 (200 views) active last 24h
    num_1d_jokes_map = data.get("num_1d_users_by_jokes_viewed", {})
    
    val_100_1d = num_1d_jokes_map.get(str(100)) or num_1d_jokes_map.get(100)
    assert val_100_1d == 1
    
    val_200_1d = num_1d_jokes_map.get(str(200)) or num_1d_jokes_map.get(200)
    assert val_200_1d == 1
    
    val_50_1d = num_1d_jokes_map.get(str(50)) or num_1d_jokes_map.get(50)
    assert val_50_1d is None # User 2 not active 1d
    
    # Verify 7d stats
    # User 1 (100 views) - active < 7d
    # User 2 (50 views) - active < 7d
    # User 4 (200 views) - active < 7d
    # Expected: { "100": 1, "50": 1, "200": 1 }
    
    num_7d_map = data.get("num_7d_users_by_jokes_viewed", {})
    
    val_100 = num_7d_map.get(str(100)) or num_7d_map.get(100)
    assert val_100 == 1
    
    val_50 = num_7d_map.get(str(50)) or num_7d_map.get(50)
    assert val_50 == 1
    
    val_200 = num_7d_map.get(str(200)) or num_7d_map.get(200)
    assert val_200 == 1
    
    # Verify 7d matrix (num_7d_users_by_days_used_by_jokes_viewed)
    # User 1: Days=10, Viewed=100
    # User 4: Days=10, Viewed=200
    # User 2: Days=5, Viewed=50
    # Expected:
    # "10": { "100": 1, "200": 1 }
    # "5": { "50": 1 }
    
    matrix = data.get("num_7d_users_by_days_used_by_jokes_viewed", {})
    
    # Check Days=10 bucket
    days_10_map = matrix.get(str(10)) or matrix.get(10)
    assert days_10_map is not None
    assert (days_10_map.get(str(100)) or days_10_map.get(100)) == 1
    assert (days_10_map.get(str(200)) or days_10_map.get(200)) == 1
    
    # Check Days=5 bucket
    days_5_map = matrix.get(str(5)) or matrix.get(5)
    assert days_5_map is not None
    assert (days_5_map.get(str(50)) or days_5_map.get(50)) == 1

