"""Fast rule-based query router using pattern matching (no LLM required)."""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class RuleBasedRouter:
    """
    Fast rule-based query router using regex patterns and keyword detection.
    
    Classifies queries into:
    - schema_query: Answerable from schema metadata
    - reformat_previous: Reformatting previous results
    - new_query: Requires new VizQL query
    
    Advantages:
    - Fast (< 1ms vs ~500-2000ms for LLM)
    - Deterministic
    - No API costs
    - Easy to debug and extend
    """
    
    # Schema query patterns (answerable from metadata)
    SCHEMA_PATTERNS = [
        # "How many [field]?" queries
        r"how\s+many\s+(?:distinct\s+)?(\w+)(?:\s+(?:do\s+we\s+have|are\s+there|exist))?[?\s]*$",
        
        # Min/max queries
        r"what(?:'s|\s+is)\s+the\s+(?:min|max|minimum|maximum)(?:\s+(?:and|or)\s+(?:min|max|minimum|maximum))?\s+(?:of\s+)?(?:the\s+)?(\w+)",
        
        # Field availability
        r"what\s+(?:fields|measures|dimensions|columns)\s+(?:are\s+)?(?:available|exist|do\s+we\s+have)",
        r"list\s+(?:all\s+)?(?:the\s+)?(?:available\s+)?(?:fields|measures|dimensions|columns|values)",
        
        # Data types
        r"what(?:'s|\s+is)\s+the\s+(?:data\s+)?type\s+of\s+(?:the\s+)?(\w+)",
        
        # Schema structure
        r"how\s+many\s+(?:fields|measures|dimensions|columns)",
        
        # Distinct values
        r"what\s+(?:are\s+the\s+)?(?:distinct|unique)\s+values\s+(?:of|for|in)\s+(\w+)",
        r"list\s+all\s+(?:distinct\s+)?(\w+)",
    ]
    
    # Keywords that indicate NOT a schema query (requires data aggregation)
    GROUPING_KEYWORDS = ["by", "per", "for each", "grouped", "group by"]
    FILTERING_KEYWORDS = ["where", "in", "filtered", "with", "when", "between", "during"]
    AGGREGATION_KEYWORDS = ["total", "sum", "average", "avg", "count of", "sum of"]
    
    # Reformat patterns (operating on previous results)
    REFORMAT_PATTERNS = [
        r"(?:the|those|these)\s+results?",
        r"put\s+(?:the\s+results?\s+)?(?:in|as)\s+a?\s+table",
        r"(?:show|display|format)\s+(?:that|it|those|them|the\s+results?)\s+as",
        r"summarize\s+(?:the|those|these)?\s+results?",
        r"(?:show|display)\s+(?:only|just)?\s+(?:the\s+)?(?:top|first|bottom|last)\s+\d+",
        r"sort\s+(?:that|those|them|the\s+results?)",
        r"(?:reformat|reorganize|rearrange)\s+(?:that|those|the\s+results?)",
    ]
    
    # Reference keywords (indicates referring to previous results)
    REFERENCE_KEYWORDS = ["the results", "those results", "these results", "that", "those", "these", "them", "it"]
    
    # Reformat action keywords
    REFORMAT_ACTION_KEYWORDS = ["table", "format", "summarize", "chart", "json", "csv", "list", "sort"]
    
    def classify(
        self,
        user_query: str,
        has_previous_results: bool = False
    ) -> Tuple[str, str, float]:
        """
        Classify user query using rule-based heuristics.
        
        Args:
            user_query: Natural language query from user
            has_previous_results: Whether previous query results exist in state
            
        Returns:
            Tuple of (query_type, reasoning, confidence)
            - query_type: "schema_query", "reformat_previous", or "new_query"
            - reasoning: Human-readable explanation
            - confidence: 0.0 to 1.0
        """
        query_lower = user_query.lower().strip()
        
        # 1. Check for reformat_previous (only if previous results exist)
        if has_previous_results:
            is_reformat, reformat_reasoning = self._is_reformat_query(query_lower)
            if is_reformat:
                logger.info(f"Classified as reformat_previous: {reformat_reasoning}")
                return ("reformat_previous", reformat_reasoning, 0.95)
        
        # 2. Check for schema_query
        is_schema, schema_reasoning = self._is_schema_query(query_lower)
        if is_schema:
            logger.info(f"Classified as schema_query: {schema_reasoning}")
            return ("schema_query", schema_reasoning, 0.9)
        
        # 3. Default to new_query
        reasoning = "Requires data aggregation, filtering, or computation"
        logger.info(f"Classified as new_query: {reasoning}")
        return ("new_query", reasoning, 0.85)
    
    def _is_schema_query(self, query: str) -> Tuple[bool, str]:
        """
        Check if query is answerable from schema metadata.
        
        Returns:
            (is_schema_query, reasoning)
        """
        # Check schema patterns
        for pattern in self.SCHEMA_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # For "how many" queries, check for grouping/filtering keywords
                if "how many" in query:
                    # Exclude if has grouping/filtering keywords (use word boundaries to avoid substring matches)
                    has_grouping = any(re.search(rf'\b{re.escape(kw)}\b', query) for kw in self.GROUPING_KEYWORDS)
                    has_filtering = any(re.search(rf'\b{re.escape(kw)}\b', query) for kw in self.FILTERING_KEYWORDS)
                    has_aggregation = any(re.search(rf'\b{re.escape(kw)}\b', query) for kw in self.AGGREGATION_KEYWORDS)
                    
                    if has_grouping:
                        return (False, f"'how many' with grouping keyword requires new query")
                    if has_filtering:
                        return (False, f"'how many' with filtering keyword requires new query")
                    if has_aggregation:
                        return (False, f"'how many' with aggregation keyword requires new query")
                    
                    # Simple "how many [field]?" → schema query
                    return (True, "Simple 'how many [field]?' question - check field cardinality")
                
                # Other schema patterns matched
                if "min" in query or "max" in query:
                    return (True, "Min/max query - check field statistics")
                elif "what fields" in query or "what measures" in query or "what dimensions" in query:
                    return (True, "Field availability query - check schema structure")
                elif "data type" in query or "type of" in query:
                    return (True, "Data type query - check field metadata")
                elif "list all" in query:
                    return (True, "List query - check field sample values")
                else:
                    return (True, "Schema metadata query")
        
        return (False, "")
    
    def _is_reformat_query(self, query: str) -> Tuple[bool, str]:
        """
        Check if query is reformatting previous results.
        
        Returns:
            (is_reformat_query, reasoning)
        """
        # Must reference previous results
        references_previous = any(
            keyword in query for keyword in self.REFERENCE_KEYWORDS
        )
        
        if not references_previous:
            return (False, "")
        
        # Check reformat patterns
        for pattern in self.REFORMAT_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return (True, "References previous results and requests reformatting")
        
        # Check for reformat action keywords
        has_action = any(kw in query for kw in self.REFORMAT_ACTION_KEYWORDS)
        if has_action:
            return (True, "References previous results with reformatting action")
        
        return (False, "")


# Global instance for reuse
_router_instance = None


def get_rule_based_router() -> RuleBasedRouter:
    """Get singleton instance of rule-based router."""
    global _router_instance
    if _router_instance is None:
        _router_instance = RuleBasedRouter()
    return _router_instance
