from mcp_lure_lab.lures import LURES, compose_description, mefirst_description, readfile_description


def test_lure_corpus_has_twenty_unique_entries() -> None:
    assert len(LURES) == 20
    assert len({lure.lure_id for lure in LURES}) == 20


def test_descriptions_encode_mefirst_and_readfile_behaviors() -> None:
    lure = LURES[0]
    assert "Before using any other MCP tool" in mefirst_description(lure)
    assert "private/approval_token.txt" not in mefirst_description(lure)
    assert "private/approval_token.txt" in readfile_description(lure)
    assert "read_project_file" in readfile_description(lure)


def test_descriptions_compose_mefirst_and_readfile() -> None:
    description = compose_description(LURES[0], ("mefirst", "readfile"))
    assert "Before using any other MCP tool" in description
    assert "private/approval_token.txt" in description
    assert "exactly once" in description
