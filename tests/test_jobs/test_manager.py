"""Tests for job manager CRUD operations.

Validates job lifecycle management: create, status updates, progress tracking,
error logging, and checkpoint save.
"""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from feedops.jobs.models import BackfillJob, JobError, JobStatus, JobType


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client with table operation tracking."""
    mock_client = MagicMock()

    # Storage for simulating database state
    jobs_storage = {}
    errors_storage = []

    def insert_job(data):
        """Simulate job insertion."""
        job_id = str(uuid4())
        job_data = {**data, "id": job_id}
        jobs_storage[job_id] = job_data

        result = MagicMock()
        result.data = [job_data]
        return result

    def select_job(job_id):
        """Simulate job selection."""
        result = MagicMock()
        if job_id in jobs_storage:
            result.data = [jobs_storage[job_id]]
        else:
            result.data = []
        return result

    def update_job(job_id, updates):
        """Simulate job update."""
        if job_id in jobs_storage:
            jobs_storage[job_id].update(updates)
        result = MagicMock()
        return result

    def insert_error(data):
        """Simulate error insertion."""
        error_data = {**data, "id": len(errors_storage) + 1}
        errors_storage.append(error_data)
        result = MagicMock()
        result.data = [error_data]
        return result

    def increment_failures(params):
        """Simulate RPC increment_backfill_failures."""
        job_id = params["p_job_id"]
        if job_id in jobs_storage:
            jobs_storage[job_id]["failed_items"] = jobs_storage[job_id].get("failed_items", 0) + 1
        result = MagicMock()
        return result

    # Configure mock to handle table operations
    def table(table_name):
        table_mock = MagicMock()

        if table_name == "backfill_jobs":
            def insert(data):
                insert_result = insert_job(data)
                execute_mock = MagicMock()
                execute_mock.execute = MagicMock(return_value=insert_result)
                return execute_mock

            def select(columns):
                select_mock = MagicMock()

                def eq(column, value):
                    eq_result = select_job(value)
                    execute_mock = MagicMock()
                    execute_mock.execute = MagicMock(return_value=eq_result)
                    return execute_mock

                select_mock.eq = eq
                return select_mock

            def update(updates):
                update_mock = MagicMock()

                def eq(column, value):
                    update_result = update_job(value, updates)
                    execute_mock = MagicMock()
                    execute_mock.execute = MagicMock(return_value=update_result)
                    return execute_mock

                update_mock.eq = eq
                return update_mock

            table_mock.insert = insert
            table_mock.select = select
            table_mock.update = update

        elif table_name == "backfill_job_errors":
            def insert(data):
                insert_result = insert_error(data)
                execute_mock = MagicMock()
                execute_mock.execute = MagicMock(return_value=insert_result)
                return execute_mock

            table_mock.insert = insert

        return table_mock

    def rpc(func_name, params):
        """Simulate RPC calls."""
        if func_name == "increment_backfill_failures":
            rpc_result = increment_failures(params)
        else:
            rpc_result = MagicMock()

        execute_mock = MagicMock()
        execute_mock.execute = MagicMock(return_value=rpc_result)
        return execute_mock

    mock_client.table = table
    mock_client.rpc = rpc
    mock_client._jobs_storage = jobs_storage
    mock_client._errors_storage = errors_storage

    return mock_client


@patch("feedops.db.supabase_client.get_client")
def test_create_job(mock_get_client, mock_supabase):
    """Test creating a backfill job."""
    from feedops.jobs.manager import create_job

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1", "SKU-2"],
        config={"batch_size": 10},
        created_by="test_user"
    )

    # Verify job was created
    assert job_id is not None
    assert job_id in mock_supabase._jobs_storage

    # Verify job data
    job_data = mock_supabase._jobs_storage[job_id]
    assert job_data["job_type"] == "search_terms"
    assert job_data["status"] == "creating"
    assert job_data["total_items"] == 2
    assert job_data["completed_items"] == 0
    assert job_data["failed_items"] == 0
    assert job_data["skus"] == ["SKU-1", "SKU-2"]
    assert job_data["config"] == {"batch_size": 10}
    assert job_data["created_by"] == "test_user"


@patch("feedops.db.supabase_client.get_client")
def test_update_job_status_to_running(mock_get_client, mock_supabase):
    """Test updating job status to running sets started_at."""
    from feedops.jobs.manager import create_job, update_job_status, get_job

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"],
    )

    # Update status to running
    update_job_status(job_id, "running")

    # Verify started_at was set
    job = get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.RUNNING
    assert job.started_at is not None


@patch("feedops.db.supabase_client.get_client")
def test_update_job_status_to_complete(mock_get_client, mock_supabase):
    """Test updating job status to complete sets completed_at."""
    from feedops.jobs.manager import create_job, update_job_status

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"],
    )

    # Update status to complete
    update_job_status(job_id, "complete")

    # Verify completed_at was set
    job_data = mock_supabase._jobs_storage[job_id]
    assert job_data["status"] == "complete"
    assert job_data["completed_at"] is not None


@patch("feedops.db.supabase_client.get_client")
def test_update_job_progress_with_eta(mock_get_client, mock_supabase):
    """Test that progress updates calculate ETA correctly."""
    from feedops.jobs.manager import create_job, update_job_progress

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"] * 100,
    )

    # Update progress: 50/100 items after 50 seconds
    started_at_epoch = time.time() - 50
    update_job_progress(
        job_id,
        completed_items=50,
        total_items=100,
        started_at_epoch=started_at_epoch
    )

    # Verify ETA is approximately 50 seconds (remaining 50 items at 1 item/sec)
    job_data = mock_supabase._jobs_storage[job_id]
    eta = job_data.get("eta_seconds")
    assert eta is not None
    # Allow ±5 seconds tolerance
    assert 45 <= eta <= 55, f"Expected ETA ~50s, got {eta}s"


@patch("feedops.db.supabase_client.get_client")
def test_log_job_error(mock_get_client, mock_supabase):
    """Test logging a job error."""
    from feedops.jobs.manager import create_job, log_job_error

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"],
    )

    # Log error
    log_job_error(
        job_id,
        item_id="SKU-1",
        error_type="api_error",
        error_message="Rate limited",
        retry_count=1
    )

    # Verify error was inserted
    assert len(mock_supabase._errors_storage) == 1
    error = mock_supabase._errors_storage[0]
    assert error["job_id"] == job_id
    assert error["item_id"] == "SKU-1"
    assert error["error_type"] == "api_error"
    assert error["error_message"] == "Rate limited"
    assert error["retry_count"] == 1

    # Verify failed_items was incremented
    job_data = mock_supabase._jobs_storage[job_id]
    assert job_data["failed_items"] == 1


@patch("feedops.db.supabase_client.get_client")
def test_log_job_error_truncates_message(mock_get_client, mock_supabase):
    """Test that error messages are truncated to 500 characters."""
    from feedops.jobs.manager import create_job, log_job_error

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"],
    )

    # Log error with 600-character message
    long_message = "A" * 600
    log_job_error(
        job_id,
        item_id="SKU-1",
        error_type="api_error",
        error_message=long_message,
    )

    # Verify message was truncated to 500 chars
    error = mock_supabase._errors_storage[0]
    assert len(error["error_message"]) == 500


@patch("feedops.db.supabase_client.get_client")
def test_save_checkpoint(mock_get_client, mock_supabase):
    """Test saving checkpoint data."""
    from feedops.jobs.manager import create_job, save_checkpoint

    mock_get_client.return_value = mock_supabase

    # Create job
    job_id = create_job(
        job_type="search_terms",
        skus=["SKU-1"] * 100,
    )

    # Save checkpoint
    checkpoint_data = {
        "batch_index": 50,
        "last_item": "SKU-50"
    }
    save_checkpoint(job_id, checkpoint_data)

    # Verify checkpoint was saved
    job_data = mock_supabase._jobs_storage[job_id]
    assert job_data["checkpoint_data"] == checkpoint_data
