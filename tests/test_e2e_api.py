import httpx
import asyncio

async def test_all_endpoints():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        routes = [
            "/",
            "/inventory",
            "/expiry",
            "/order-plan",
            "/matching",
            "/users",
            "/api/auth/me",
            "/api/products",
            "/api/warehouses",
            "/api/inventory/summary",
            "/api/expiry/summary",
            "/api/order-plan?target_month=2026-06",
            "/api/matching/status"
        ]
        
        print("Starting QA Orchestration Loop...")
        all_passed = True
        for route in routes:
            try:
                res = await client.get(route)
                if res.status_code == 200:
                    print(f"[PASS] {route} -> 200 OK")
                else:
                    print(f"[FAIL] {route} -> {res.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"[ERROR] {route} -> {str(e)}")
                all_passed = False
                
        if all_passed:
            print("\nALL TESTS PASSED: Orchestration QA Successful!")
        else:
            print("\nSOME TESTS FAILED: Please fix errors.")

asyncio.run(test_all_endpoints())
