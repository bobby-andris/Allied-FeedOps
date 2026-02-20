from feedops.cli.main import _fetch_variant_index_rows


class _ExecuteResult:
    def __init__(self, data):
        self.data = data


class _RangeQuery:
    def __init__(self, parent, start, end):
        self.parent = parent
        self.start = start
        self.end = end

    def execute(self):
        self.parent.calls.append((self.start, self.end))
        if self.start == 0:
            return _ExecuteResult([{"master_sku": f"SKU-{i}", "gmc_offer_id": f"offer-{i}", "custom_labels": {}} for i in range(1000)])
        if self.start == 1000:
            return _ExecuteResult([{"master_sku": f"SKU-{1000+i}", "gmc_offer_id": f"offer-{1000+i}", "custom_labels": {}} for i in range(1000)])
        if self.start == 2000:
            return _ExecuteResult([{"master_sku": f"SKU-{2000+i}", "gmc_offer_id": f"offer-{2000+i}", "custom_labels": {}} for i in range(200)])
        return _ExecuteResult([])


class _SelectQuery:
    def __init__(self, parent):
        self.parent = parent

    def range(self, start, end):
        return _RangeQuery(self.parent, start, end)


class _TableQuery:
    def __init__(self):
        self.calls = []

    def select(self, _columns):
        return _SelectQuery(self)


class _SupabaseStub:
    def __init__(self):
        self.table_query = _TableQuery()

    def table(self, _name):
        return self.table_query


def test_fetch_variant_index_rows_paginates_beyond_supabase_default_cap():
    supabase = _SupabaseStub()

    rows = _fetch_variant_index_rows(supabase)

    assert len(rows) == 2200
    assert supabase.table_query.calls[:3] == [
        (0, 999),
        (1000, 1999),
        (2000, 2999),
    ]
