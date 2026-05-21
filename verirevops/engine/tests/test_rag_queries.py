import unittest

from src.core.queries import (
    HYBRID_DOCUMENT_SEARCH_QUERY,
    INSERT_CHILD_DOCUMENT_QUERY,
    INSERT_PARENT_DOCUMENT_QUERY,
)


class RagQueryTests(unittest.TestCase):
    def test_hybrid_search_query_formats_without_filters(self):
        query = HYBRID_DOCUMENT_SEARCH_QUERY.format(filter_clause="")

        self.assertNotIn("{filter_clause}", query)
        self.assertIn(":emb", query)
        self.assertIn(":tid", query)
        self.assertIn(":lim", query)
        self.assertIn(":msg", query)

    def test_hybrid_search_query_applies_filters_to_vector_and_keyword_search(self):
        filter_clause = " AND metadata_->>'source' = :meta_0"
        query = HYBRID_DOCUMENT_SEARCH_QUERY.format(filter_clause=filter_clause)

        self.assertEqual(query.count(filter_clause), 2)

    def test_document_insert_queries_keep_expected_params(self):
        self.assertIn(":tenant", INSERT_PARENT_DOCUMENT_QUERY)
        self.assertIn(":file", INSERT_PARENT_DOCUMENT_QUERY)
        self.assertIn(":content", INSERT_PARENT_DOCUMENT_QUERY)
        self.assertIn(":meta", INSERT_PARENT_DOCUMENT_QUERY)

        self.assertIn(":tenant", INSERT_CHILD_DOCUMENT_QUERY)
        self.assertIn(":file", INSERT_CHILD_DOCUMENT_QUERY)
        self.assertIn(":content", INSERT_CHILD_DOCUMENT_QUERY)
        self.assertIn(":emb", INSERT_CHILD_DOCUMENT_QUERY)
        self.assertIn(":meta", INSERT_CHILD_DOCUMENT_QUERY)
        self.assertIn(":pid", INSERT_CHILD_DOCUMENT_QUERY)


if __name__ == "__main__":
    unittest.main()
