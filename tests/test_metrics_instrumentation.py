# tests/test_metrics_instrumentation.py
import pytest
import time
from backend_api.src.utils.metrics import track_time, TRANSCRIPTION_DURATION

@pytest.mark.asyncio
async def test_track_time_decorator():
    @track_time(TRANSCRIPTION_DURATION)
    async def dummy_function():
        time.sleep(0.1)
        return "done"
    
    result = await dummy_function()
    assert result == "done"
    
    # Check that the histogram has recorded a value (internal _sum should be greater than zero).
    # (Note: Accessing internal attributes is not ideal in production tests,
    # but it provides confirmation here.)
    assert TRANSCRIPTION_DURATION._sum > 0
