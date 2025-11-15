"""
Basic Usage Examples for Manus-ScrapeX
"""
import asyncio
import requests

# API base URL
API_URL = "http://localhost:8000"


def example_1_simple_scrape():
    """Example 1: Simple product scraping"""
    print("=== Example 1: Simple Product Scraping ===\n")

    payload = {
        "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "schema": {
            "title": {
                "type": "string",
                "description": "Book title",
                "required": True
            },
            "price": {
                "type": "float",
                "description": "Book price in GBP",
                "required": True
            },
            "availability": {
                "type": "string",
                "description": "Stock availability status",
                "required": False
            }
        }
    }

    response = requests.post(f"{API_URL}/api/v1/scrape", json=payload)
    result = response.json()

    if result["success"]:
        print("✓ Success!")
        print(f"Title: {result['data']['data']['title']}")
        print(f"Price: £{result['data']['data']['price']}")
        print(f"Availability: {result['data']['data']['availability']}")
        print(f"Execution time: {result['data']['execution_time']:.2f}s\n")
    else:
        print(f"✗ Error: {result['error']}\n")


def example_2_ecommerce():
    """Example 2: E-commerce product data"""
    print("=== Example 2: E-commerce Product ===\n")

    payload = {
        "url": "https://www.scrapethissite.com/pages/ajax-javascript/",
        "schema": {
            "title": {
                "type": "string",
                "description": "Page main title or heading",
                "required": True
            },
            "description": {
                "type": "string",
                "description": "Page description or intro text",
                "required": False
            }
        },
        "options": {
            "screenshot": False,
            "timeout": 30
        }
    }

    response = requests.post(f"{API_URL}/api/v1/scrape", json=payload)
    result = response.json()

    if result["success"]:
        print("✓ Success!")
        for key, value in result['data']['data'].items():
            print(f"{key}: {value}")
        print()
    else:
        print(f"✗ Error: {result['error']}\n")


def example_3_batch_scraping():
    """Example 3: Batch scraping multiple URLs"""
    print("=== Example 3: Batch Scraping ===\n")

    # Define schema once
    schema = {
        "title": {
            "type": "string",
            "description": "Book title",
            "required": True
        },
        "price": {
            "type": "float",
            "description": "Book price",
            "required": True
        }
    }

    # Multiple URLs
    urls = [
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
        "https://books.toscrape.com/catalogue/soumission_998/index.html"
    ]

    payload = [
        {"url": url, "schema": schema, "priority": 1}
        for url in urls
    ]

    response = requests.post(f"{API_URL}/api/v1/scrape/batch", json=payload)
    result = response.json()

    print(f"Total: {result['total']}")
    print(f"Completed: {result['completed']}")
    print(f"Failed: {result['failed']}\n")

    for i, item in enumerate(result['results'], 1):
        if item['success']:
            print(f"{i}. {item['data']['title']} - £{item['data']['price']}")
        else:
            print(f"{i}. Error: {item['error']}")

    print()


def example_4_check_status():
    """Example 4: Check system status"""
    print("=== Example 4: System Status ===\n")

    response = requests.get(f"{API_URL}/api/v1/status")
    status = response.json()

    print(f"Status: {status['status']}")
    print(f"Version: {status['version']}")
    print(f"Environment: {status['environment']}")

    # LLM metrics
    if 'llm_metrics' in status:
        metrics = status['llm_metrics']
        print(f"\nLLM Metrics:")
        print(f"  Total requests: {metrics['total_requests']}")
        print(f"  Success rate: {metrics['success_rate']:.1%}")
        print(f"  Average latency: {metrics['average_latency']:.2f}s")
        print(f"  Total cost: ${metrics['total_cost_usd']:.4f}")

    # Proxy stats
    if 'proxy_stats' in status:
        proxies = status['proxy_stats']
        print(f"\nProxy Pool:")
        print(f"  Total proxies: {proxies['total_proxies']}")
        print(f"  Healthy proxies: {proxies['healthy_proxies']}")

    print()


def example_5_validate_schema():
    """Example 5: Validate extraction schema"""
    print("=== Example 5: Schema Validation ===\n")

    # Valid schema
    schema = {
        "price": {
            "type": "float",
            "description": "Product price",
            "required": True
        },
        "rating": {
            "type": "float",
            "description": "Product rating (0-5)",
            "required": False
        }
    }

    response = requests.post(f"{API_URL}/api/v1/validate-schema", json=schema)
    result = response.json()

    if result['valid']:
        print(f"✓ Schema is valid ({result['field_count']} fields)")
    else:
        print(f"✗ Schema has errors:")
        for error in result['errors']:
            print(f"  - {error}")

    print()


def run_all_examples():
    """Run all examples"""
    print("\n" + "="*60)
    print(" Manus-ScrapeX - Usage Examples")
    print("="*60 + "\n")

    # Check if API is running
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code != 200:
            print("❌ API is not running. Please start it first:")
            print("   docker-compose up -d")
            print("   OR: make run-api")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API at", API_URL)
        print("   Please start the API server first.")
        return

    print("✓ API is running\n")

    # Run examples
    example_1_simple_scrape()
    example_2_ecommerce()
    example_3_batch_scraping()
    example_4_check_status()
    example_5_validate_schema()

    print("="*60)
    print("All examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_examples()
