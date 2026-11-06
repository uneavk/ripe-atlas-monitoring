"""Compatibility entry point: measurement storage and rollups are ClickHouse-only."""
from .retention_clickhouse import *
if __name__=='__main__':main()
