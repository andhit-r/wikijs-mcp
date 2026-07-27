"""Validasi seluruh dokumen GraphQL ``tools/groups.py`` terhadap SDL Wiki.js 2.x.

Mencegah regresi ``andhit-r/wikijs-mcp#4``: ``wikijs_group_get`` dan
``wikijs_group_update`` selalu gagal HTTP 400 ``GRAPHQL_VALIDATION_FAILED``
terhadap Wiki.js sungguhan, sementara unit test respx tetap hijau karena
mock-nya memantulkan kembali bentuk yang sama-sama salah dengan query
produksinya.

Modul ``ast`` dipakai untuk mengekstrak literal string yang di-assign ke
nama ``query``/``mutation`` di ``src/wikijs_mcp/tools/groups.py`` — TANPA
mengubah bentuk kode produksi (bukan menyalin ulang query di test) — lalu
tiap dokumen di-parse dan divalidasi (``graphql-core``) terhadap SDL yang
di-commit di ``tests/schema/wikijs-2.x.graphql``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from graphql import GraphQLSchema, build_schema, parse, validate

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GROUPS_TOOL_PATH = _REPO_ROOT / "src" / "wikijs_mcp" / "tools" / "groups.py"
_SCHEMA_PATH = _REPO_ROOT / "tests" / "schema" / "wikijs-2.x.graphql"

# Jumlah literal query/mutation yang diharapkan ditemukan di tools/groups.py:
# group_list (query), group_get (query), group_create (mutation),
# _fetch_current_for_update (query, helper read-modify-write group_update),
# group_update (mutation), group_delete (mutation), group_assign_user
# (mutation), group_unassign_user (mutation). Angka ini sengaja di-assert
# eksplisit agar ekstraktor AST yang diam-diam berhenti menemukan dokumen
# (mis. gara-gara refactor nama variabel) tidak membuat gate ini selalu
# hijau tanpa benar-benar memvalidasi apa pun.
_EXPECTED_DOCUMENT_COUNT = 8


def _extract_graphql_documents(source_path: Path) -> list[str]:
    """Ekstrak seluruh literal string GraphQL dari sebuah modul tool.

    Menelusuri AST modul dan mengambil nilai literal string tiap statement
    assignment bernama ``query`` atau ``mutation`` (mis.
    ``query = \"\"\"...\"\"\"``) — pola yang dipakai seluruh tool GraphQL di
    project ini. Tidak mengeksekusi ataupun mengubah kode sumbernya.

    Args:
        source_path: Path berkas Python yang akan diparse.

    Returns:
        Daftar string dokumen GraphQL (belum di-parse ke AST GraphQL).
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    documents: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        target_names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not ({"query", "mutation"} & target_names):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            documents.append(node.value.value)
    return documents


@pytest.fixture(scope="module")
def wikijs_schema() -> GraphQLSchema:
    """SDL Wiki.js 2.x domain ``groups`` yang di-commit, di-parse ke ``GraphQLSchema``."""
    return build_schema(_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def groups_documents() -> list[str]:
    """Seluruh literal ``query``/``mutation`` GraphQL di ``tools/groups.py``."""
    documents = _extract_graphql_documents(_GROUPS_TOOL_PATH)
    assert documents, "tidak ada literal query/mutation ditemukan di groups.py"
    return documents


def test_document_count_matches_expected(groups_documents: list[str]) -> None:
    """Regresi cakupan ekstraktor: jumlah dokumen terekstrak sesuai ekspektasi."""
    assert len(groups_documents) == _EXPECTED_DOCUMENT_COUNT


def test_all_groups_documents_valid_against_schema(
    wikijs_schema: GraphQLSchema, groups_documents: list[str]
) -> None:
    """Positif: seluruh dokumen GraphQL ``tools/groups.py`` lolos ``graphql.validate``."""
    for document in groups_documents:
        errors = validate(wikijs_schema, parse(document))
        assert errors == [], f"Dokumen GraphQL tidak valid terhadap SDL:\n{errors}\n{document}"


def test_validator_rejects_user_count_on_group(wikijs_schema: GraphQLSchema) -> None:
    """Negatif: dokumen sintetis yang menyeleksi ``userCount`` pada ``Group`` ditolak.

    Membuktikan gate ini benar-benar menangkap ketidakcocokan skema (bug asli
    ``andhit-r/wikijs-mcp#4``), bukan validator yang selalu hijau apa pun
    isi dokumennya.
    """
    bad_document = """
    query($id: Int!) {
      groups {
        single(id: $id) {
          id
          userCount
        }
      }
    }
    """
    errors = validate(wikijs_schema, parse(bad_document))
    assert errors, "validator seharusnya menolak userCount pada tipe Group"
    assert any("userCount" in str(error) for error in errors)
