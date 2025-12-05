from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class RunRequest(BaseModel):
    """Request payload to trigger a Robot Framework test run."""
    project: Optional[str] = Field(None, description="Project or profile name")
    suite: Optional[str] = Field(None, description="Suite name to run")
    tests: Optional[List[str]] = Field(None, description="List of test case names to run")
    include_tags: Optional[List[str]] = Field(None, description="Include tests with these tags")
    exclude_tags: Optional[List[str]] = Field(None, description="Exclude tests with these tags")
    variables: Optional[Dict[str, Any]] = Field(None, description="Extra variables passed to Robot")
    loop: Optional[int] = Field(1, description="Number of times to repeat the run (loop count)")
    batch: Optional[bool] = Field(False, description="Indicates a batch run")
    dry_run: Optional[bool] = Field(False, description="Run Robot in dry-run mode (no execution)")


# PUBLIC_INTERFACE
class RunResponse(BaseModel):
    """Response payload after scheduling a run."""
    run_id: int = Field(..., description="Database ID of the TestRun")
    status: str = Field(..., description="Initial status of the run")
    logs_path: Optional[str] = Field(None, description="Filesystem path where logs are written")


# PUBLIC_INTERFACE
class StopResponse(BaseModel):
    """Response payload after stopping a run."""
    run_id: Optional[int] = Field(None, description="Stopped run id if any")
    stopped: bool = Field(..., description="Whether a running process was stopped")


# PUBLIC_INTERFACE
class StatsResponse(BaseModel):
    """Aggregated statistics for a run."""
    run_id: int = Field(..., description="Run id")
    total: int = Field(..., description="Total test cases expected")
    passed: int = Field(..., description="Passed count so far")
    failed: int = Field(..., description="Failed count so far")
    status: str = Field(..., description="Run status")


# PUBLIC_INTERFACE
class CaseStatusResponse(BaseModel):
    """Current per-case status summary."""
    run_id: int = Field(..., description="Run id")
    passed: int = Field(..., description="Number of passed cases")
    failed: int = Field(..., description="Number of failed cases")
    total_recorded: int = Field(..., description="Total cases recorded in DB")


# PUBLIC_INTERFACE
class ProgressResponse(BaseModel):
    """Run progress information."""
    run_id: int = Field(..., description="Run id")
    completed: int = Field(..., description="Number of completed cases")
    total: int = Field(..., description="Expected total cases")
    percent: float = Field(..., description="Completion percentage (0-100)")


# PUBLIC_INTERFACE
class CurrentCaseInfo(BaseModel):
    """Information about the currently executing case, if available."""
    run_id: int = Field(..., description="Run id")
    case_name: Optional[str] = Field(None, description="Current case name")
    suite_name: Optional[str] = Field(None, description="Current suite name")
    start_time: Optional[datetime] = Field(None, description="Start time of current case")


# PUBLIC_INTERFACE
class ConfigPayload(BaseModel):
    """Config content read/written via API."""
    path: str = Field(..., description="Relative path to the config file from CONFIG_DIR")
    content: Dict[str, Any] = Field(..., description="Parsed YAML/JSON content of the config")


# PUBLIC_INTERFACE
class ConfigListResponse(BaseModel):
    """List of sub-folders available under the configuration directory."""
    folders: List[str] = Field(..., description="Relative folder names under CONFIG_DIR")


# PUBLIC_INTERFACE
class UILockRequest(BaseModel):
    """Lock/unlock the UI to prevent concurrent actions."""
    locked: bool = Field(..., description="Whether the UI should be locked")
    owner: Optional[str] = Field(None, description="Identifier for the lock owner")


# PUBLIC_INTERFACE
class SyncStateRequest(BaseModel):
    """Set or synchronize arbitrary UI/app state variables."""
    state: Dict[str, Any] = Field(..., description="Arbitrary state map")


# PUBLIC_INTERFACE
class GetStateResponse(BaseModel):
    """Return the currently stored UI/app state variables."""
    state: Dict[str, Any] = Field(..., description="Arbitrary state map")


# PUBLIC_INTERFACE
class ExpectedTotalResponse(BaseModel):
    """Get or set the expected total case count for a run."""
    run_id: int = Field(..., description="Run id")
    expected_total: int = Field(..., description="Expected total test cases")
