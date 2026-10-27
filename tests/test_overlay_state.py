"""Missing overlay is an explicit recoverable state, never an endless spinner."""
import pytest
from services.api.overlay_state import overlay_state


@pytest.mark.parametrize("inputs,expected",[
 (dict(ready=True,video_exists=True,source_exists=True,job_active=False,
       attempted=True,last_status="failed"),"available"),
 (dict(ready=True,video_exists=False,source_exists=False,job_active=False,
       attempted=False,last_status="completed"),"source_missing"),
 (dict(ready=True,video_exists=False,source_exists=True,job_active=False,
       attempted=False,last_status=None),"auto_rebuild"),
 (dict(ready=True,video_exists=False,source_exists=True,job_active=True,
       attempted=True,last_status=None),"rendering"),
 (dict(ready=True,video_exists=False,source_exists=True,job_active=False,
       attempted=True,last_status=None),"needs_retry"),
 (dict(ready=True,video_exists=False,source_exists=True,job_active=False,
       attempted=True,last_status="failed"),"failed"),
 (dict(ready=False,video_exists=False,source_exists=True,job_active=False,
       attempted=False,last_status=None),"case_not_ready"),
])
def test_states(inputs,expected):
    assert overlay_state(**inputs)==expected


def test_no_success_from_old_database_metadata():
    result=overlay_state(ready=True,video_exists=False,source_exists=True,
                         job_active=False,attempted=True,last_status="completed")
    assert result=="needs_retry"
