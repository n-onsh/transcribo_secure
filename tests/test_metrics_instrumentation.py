import pytest
import time
from transcriber.src.utils.metrics import track_time, TRANSCRIPTION_DURATION

@pytest.mark.asyncio
async def test_track_time_decorator():
    @track_time(TRANSCRIPTION_DURATION)
    async def dummy_function():
        # Use a non-blocking sleep in async context.
        import asyncio
        await asyncio.sleep(0.1)
        return "done"
    
    result = await dummy_function()
    assert result == "done"
    
    # Extract the _sum from the collected metrics.
    collected = list(TRANSCRIPTION_DURATION.collect())
    sum_value = None
    for metric in collected:
        for sample in metric.samples:
            if sample.name.endswith("_sum"):
                sum_value = sample.value
                break
        if sum_value is not None:
            break
    assert sum_value is not None, "Histogram sum not found."
    assert sum_value > 0
