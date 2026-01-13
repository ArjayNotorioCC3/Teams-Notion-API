"""
Pre-validation test endpoint for Microsoft Graph compatibility.

This endpoint simulates the validation request that Microsoft Graph sends
and measures the actual round-trip time including network latency.
"""
import logging
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pre-validation", tags=["pre-validation"])


@router.get("/test")
async def test_pre_validation(request: Request):
    """
    Test endpoint to simulate Microsoft Graph validation.
    
    This endpoint measures the full round-trip time for validation requests,
    including network latency. Microsoft Graph sends validation requests
    like: GET /webhook/notification?validationToken=xxx
    
    Returns:
        Validation token with response time in headers
    """
    start_time = time.perf_counter()
    
    validation_token = request.query_params.get("validationToken")
    
    if not validation_token:
        raise HTTPException(status_code=400, detail="Missing validationToken")
    
    # Calculate response time in microseconds
    elapsed_us = (time.perf_counter() - start_time) * 1_000_000
    elapsed_ms = elapsed_us / 1000.0
    
    logger.info(f"Pre-validation test - Response time: {elapsed_us:.0f}μs ({elapsed_ms:.2f}ms)")
    
    # Log warnings for slow response times
    if elapsed_ms > 100:
        logger.warning(f"Pre-validation test - Slow response time: {elapsed_ms:.2f}ms")
    elif elapsed_ms > 50:
        logger.warning(f"Pre-validation test - Elevated response time: {elapsed_ms:.2f}ms")
    
    # Return validation token with timing info in headers
    return PlainTextResponse(
        content=validation_token,
        status_code=200,
        headers={
            "X-Response-Time-Us": str(int(elapsed_us)),
            "X-Response-Time-Ms": f"{elapsed_ms:.2f}",
            "X-Response-Status": "PASS" if elapsed_ms < 100 else "SLOW"
        }
    )


@router.post("/test")
async def test_pre_validation_post(request: Request):
    """
    Test endpoint for POST validation (Microsoft Graph uses POST for validation).
    
    Returns:
        Validation token with response time in headers
    """
    start_time = time.perf_counter()
    
    validation_token = request.query_params.get("validationToken")
    
    if not validation_token:
        raise HTTPException(status_code=400, detail="Missing validationToken")
    
    # Calculate response time in microseconds
    elapsed_us = (time.perf_counter() - start_time) * 1_000_000
    elapsed_ms = elapsed_us / 1000.0
    
    logger.info(f"Pre-validation test (POST) - Response time: {elapsed_us:.0f}μs ({elapsed_ms:.2f}ms)")
    
    # Log warnings for slow response times
    if elapsed_ms > 100:
        logger.warning(f"Pre-validation test (POST) - Slow response time: {elapsed_ms:.2f}ms")
    elif elapsed_ms > 50:
        logger.warning(f"Pre-validation test (POST) - Elevated response time: {elapsed_ms:.2f}ms")
    
    # Return validation token with timing info in headers
    return PlainTextResponse(
        content=validation_token,
        status_code=200,
        headers={
            "X-Response-Time-Us": str(int(elapsed_us)),
            "X-Response-Time-Ms": f"{elapsed_ms:.2f}",
            "X-Response-Status": "PASS" if elapsed_ms < 100 else "SLOW"
        }
    )


@router.get("/simulate")
async def simulate_graph_validation(base_url: str = "http://localhost:8000"):
    """
    Simulate Microsoft Graph validation request and measure round-trip time.
    
    This endpoint acts like Microsoft Graph, sending a validation request
    to your webhook and measuring the full round-trip time.
    
    Args:
        base_url: Base URL of the webhook endpoint (default: http://localhost:8000)
        
    Returns:
        Validation test results including round-trip time
    """
    import httpx
    
    test_token = "test_validation_token_from_ms_graph"
    
    try:
        start_time = time.perf_counter()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Microsoft Graph sends POST request with validationToken in query params
            response = await client.post(
                f"{base_url}/webhook/notification",
                params={"validationToken": test_token},
                timeout=5.0,
                data={}  # Empty body like Microsoft Graph
            )
        
            # Measure full round-trip time
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(f"Simulated Graph validation - Round-trip time: {elapsed_ms:.2f}ms")
            
            # Validate response
            if response.status_code == 200 and response.text == test_token:
                return {
                    "success": True,
                    "round_trip_time_ms": elapsed_ms,
                    "response_status": response.status_code,
                    "response_correct": True,
                    "recommendation": "PASS" if elapsed_ms < 2000 else "FAIL",
                    "details": {
                        "round_trip_time_seconds": elapsed_ms / 1000,
                        "within_2s_limit": elapsed_ms < 2000,
                        "within_1s_limit": elapsed_ms < 1000,
                        "within_500ms_limit": elapsed_ms < 500,
                    }
                }
            else:
                return {
                    "success": False,
                    "round_trip_time_ms": elapsed_ms,
                    "response_status": response.status_code,
                    "response_correct": response.text == test_token if response.status_code == 200 else False,
                    "error": "Response validation failed" if response.status_code == 200 else f"HTTP {response.status_code}",
                    "recommendation": "CHECK_ENDPOINT"
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Timeout - endpoint did not respond in 5 seconds",
            "recommendation": "CHECK_SERVER_RUNNING"
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": "Connection refused - is the server running?",
            "recommendation": "START_SERVER"
        }
    except Exception as e:
        logger.error(f"Error simulating Graph validation: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "recommendation": "CHECK_LOGS"
        }
