"""Tests for rule-based query router."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.agents.vizql.rule_based_router import RuleBasedRouter


def run_tests():
    """Run manual tests for rule-based router."""
    router = RuleBasedRouter()
    
    test_cases = [
        # Schema queries
        ("how many customers", "schema_query", True),
        ("how many products do we have", "schema_query", True),
        ("how many distinct customers", "schema_query", True),
        ("what's the min sales", "schema_query", True),
        ("what fields are available", "schema_query", True),
        ("list all dimensions", "schema_query", True),
        
        # NOT schema queries (have grouping/filtering)
        ("how many customers by region", "new_query", True),
        ("how many customers in 2024", "new_query", True),
        
        # New queries
        ("total sales by region", "new_query", True),
        ("top 10 customers by revenue", "new_query", True),
        ("average price per product", "new_query", True),
        
        # Reformat queries (with previous results)
        ("put the results in a table", "reformat_previous", True),
        ("show that as a chart", "reformat_previous", True),
        ("summarize those results", "reformat_previous", True),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected, has_prev in test_cases:
        actual, reason, conf = router.classify(query, has_previous_results=has_prev)
        if actual == expected:
            print(f"✓ '{query}' → {actual} (conf={conf:.2f})")
            passed += 1
        else:
            print(f"✗ '{query}' → {actual} (expected {expected}, conf={conf:.2f})")
            print(f"  Reason: {reason}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed out of {len(test_cases)} tests")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
