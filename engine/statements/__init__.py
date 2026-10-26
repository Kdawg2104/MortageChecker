"""Bank statement analysis: parse, redact, categorise and summarise transactions.

Privacy by design: everything works on in-memory bytes and DataFrames. Nothing in this
package writes files, caches data or makes network calls.
"""
