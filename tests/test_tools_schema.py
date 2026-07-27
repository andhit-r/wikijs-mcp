"""Validasi seluruh dokumen GraphQL di ``src/wikijs_mcp/tools/`` terhadap SDL Wiki.js 2.x.

Generalisasi dari ``tests/test_groups_schema.py`` (``andhit-r/wikijs-mcp#4``, yang
hanya mencakup ``tools/groups.py``) ke **seluruh** modul tool
(``andhit-r/wikijs-mcp#5``), agar ketidakcocokan skema — nama field salah, subfield
hilang, nullability variabel keliru — gagal di ``make test``, bukan di produksi.

Mencegah regresi kelas bug ``andhit-r/wikijs-mcp#4``: ``wikijs_group_get`` dan
``wikijs_group_update`` selalu gagal HTTP 400 ``GRAPHQL_VALIDATION_FAILED`` terhadap
Wiki.js sungguhan, sementara unit test respx tetap hijau karena mock-nya memantulkan
kembali bentuk yang sama-sama salah dengan query produksinya.

Modul ``ast`` dipakai untuk mengekstrak literal string yang di-assign ke nama
``query``/``mutation`` di tiap modul ``src/wikijs_mcp/tools/*.py`` — TANPA mengubah
bentuk kode produksi (bukan menyalin ulang query di test) — lalu tiap dokumen
di-parse dan divalidasi (``graphql-core``) terhadap SDL yang di-commit di
``tests/schema/wikijs-2.x.graphql``.

Daftar modul yang diperiksa dibaca dari isi direktori ``src/wikijs_mcp/tools/``
(bukan ditulis tangan) — modul tool baru otomatis ikut terparametrisasi tanpa
menyentuh berkas test ini sama sekali.

Modul di :data:`_KNOWN_INVALID_MODULES` sengaja dikecualikan dari gate validasi
POSITIF (bukan diam-diam dilewati — tiap entri wajib beralasan tertulis dan diperiksa
anti-basi, lihat :func:`test_known_invalid_module_reason_is_documented` dan
:func:`test_known_invalid_module_not_stale`): temuannya menuntut perubahan semantik
kontrak tool (di luar cakupan ``andhit-r/wikijs-mcp#5``), dilacak di issue lanjutan.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from graphql import GraphQLSchema, build_schema, parse, validate

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = _REPO_ROOT / "src" / "wikijs_mcp" / "tools"
_SCHEMA_PATH = _REPO_ROOT / "tests" / "schema" / "wikijs-2.x.graphql"

# Modul yang dikecualikan dari gate validasi POSITIF beserta alasan tertulisnya.
# Setiap entri WAJIB merujuk issue lanjutan yang melacak perbaikannya. Modul di
# sini tetap WAJIB menghasilkan >=1 dokumen terekstrak (lihat
# test_module_has_extracted_documents, tidak dikecualikan dari cek itu) dan tetap
# diperiksa anti-basi: bila seluruh dokumennya ternyata sudah valid terhadap SDL,
# test_known_invalid_module_not_stale GAGAL sebagai pengingat melepas entrinya.
_KNOWN_INVALID_MODULES: dict[str, str] = {
    "users": (
        "wikijs_user_update mengirim argumen `isActive` yang TIDAK ADA pada "
        "UserMutation.update Wiki.js 2.x (server/graph/schemas/user.graphql upstream "
        "Requarks/wiki) -- status aktif hanya bisa diubah lewat mutation "
        "activate/deactivate terpisah. wikijs_user_delete mendeklarasikan $replaceId "
        "sebagai variabel nullable (Int) padahal argumen UserMutation.delete.replaceId "
        "bersifat non-null (Int!) tanpa nilai default -- Wiki.js mewajibkan replacement "
        "user id pada setiap penghapusan user, sementara signature tool ini menjanjikan "
        "replace_id opsional. Keduanya menuntut perubahan semantik kontrak tool sehingga "
        "di luar cakupan andhit-r/wikijs-mcp#5 (lihat 'Tidak termasuk'); dilacak di "
        "andhit-r/wikijs-mcp#7."
    ),
}


def _discover_tool_modules() -> list[str]:
    """Daftar nama modul tool (tanpa ``.py``) di ``src/wikijs_mcp/tools/``.

    Dibaca dari isi direktori, bukan hardcoded, agar modul tool baru otomatis
    ikut terparametrisasi oleh test ini tanpa perlu menyentuh berkas ini.

    Returns:
        Daftar nama modul terurut abjad, tanpa ``__init__``.
    """
    return sorted(path.stem for path in _TOOLS_DIR.glob("*.py") if path.stem != "__init__")


def _extract_graphql_documents(source_path: Path) -> list[str]:
    """Ekstrak seluruh literal string GraphQL dari sebuah modul tool.

    Menelusuri AST modul dan mengambil nilai literal string tiap statement
    assignment bernama ``query`` atau ``mutation`` (mis. ``query = \"\"\"...\"\"\"``)
    — pola yang dipakai seluruh tool GraphQL di project ini. Tidak mengeksekusi
    ataupun mengubah kode sumbernya.

    Args:
        source_path: Path berkas Python yang akan diparse.

    Returns:
        Daftar string dokumen GraphQL (belum di-parse ke AST GraphQL). Kosong
        bila modul tidak memuat literal ``query``/``mutation`` yang bisa
        diekstrak AST — ini kegagalan gate, bukan alasan melewati modul (lihat
        :func:`test_module_has_extracted_documents`).
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


def _all_documents_valid(schema: GraphQLSchema, documents: list[str]) -> bool:
    """Cek apakah seluruh ``documents`` lolos ``graphql.validate`` terhadap ``schema``.

    Args:
        schema: Skema Wiki.js 2.x yang di-commit.
        documents: Daftar dokumen GraphQL mentah (belum di-parse).

    Returns:
        ``True`` bila seluruh dokumen valid (tanpa error validasi), ``False``
        bila ada minimal satu dokumen yang tidak valid.
    """
    return all(validate(schema, parse(document)) == [] for document in documents)


@pytest.fixture(scope="module")
def wikijs_schema() -> GraphQLSchema:
    """SDL Wiki.js 2.x yang di-commit, di-parse ke ``GraphQLSchema``."""
    return build_schema(_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("module_name", _discover_tool_modules())
def test_module_has_extracted_documents(module_name: str) -> None:
    """Positif/negatif: tiap modul tool menghasilkan >=1 dokumen GraphQL terekstrak.

    Modul dengan nol dokumen terekstrak (mis. gara-gara pola penulisan yang tidak
    lagi cocok dengan ekstraktor AST, atau modul yang lupa memakai GraphQL sama
    sekali) membuat test ini GAGAL — gate tidak boleh diam-diam kosong untuk
    sebuah modul. Berlaku untuk SEMUA modul termasuk yang ada di
    :data:`_KNOWN_INVALID_MODULES` (pengecualian hanya berlaku untuk gate
    validasi skema positif, bukan untuk keberadaan dokumennya).
    """
    documents = _extract_graphql_documents(_TOOLS_DIR / f"{module_name}.py")
    assert documents, f"modul {module_name!r} menghasilkan nol dokumen GraphQL terekstrak"


@pytest.mark.parametrize(
    "module_name",
    sorted(set(_discover_tool_modules()) - set(_KNOWN_INVALID_MODULES)),
)
def test_module_documents_valid_against_schema(
    module_name: str, wikijs_schema: GraphQLSchema
) -> None:
    """Positif: seluruh dokumen GraphQL sebuah modul lolos ``graphql.validate``.

    Diparametrisasi per modul (dibaca dari direktori, lihat
    :func:`_discover_tool_modules`) sehingga nama modul yang gagal tampil
    langsung di laporan pytest. Modul di :data:`_KNOWN_INVALID_MODULES`
    dikecualikan dari test ini — lihat
    :func:`test_known_invalid_module_not_stale` untuk pengecekan anti-basinya.
    """
    documents = _extract_graphql_documents(_TOOLS_DIR / f"{module_name}.py")
    for document in documents:
        errors = validate(wikijs_schema, parse(document))
        assert errors == [], (
            f"Dokumen GraphQL modul {module_name!r} tidak valid terhadap SDL:\n"
            f"{errors}\n{document}"
        )


@pytest.mark.parametrize("module_name", sorted(_KNOWN_INVALID_MODULES))
def test_known_invalid_module_reason_is_documented(module_name: str) -> None:
    """Setiap entri :data:`_KNOWN_INVALID_MODULES` wajib punya alasan tertulis non-kosong."""
    reason = _KNOWN_INVALID_MODULES[module_name]
    assert reason.strip(), f"modul {module_name!r} dikecualikan tanpa alasan tertulis"


@pytest.mark.parametrize("module_name", sorted(_KNOWN_INVALID_MODULES))
def test_known_invalid_module_not_stale(module_name: str, wikijs_schema: GraphQLSchema) -> None:
    """Negatif (anti-basi): modul yang dikecualikan tapi ternyata sudah valid membuat test gagal.

    Mencegah entri :data:`_KNOWN_INVALID_MODULES` basi — bila temuan yang
    melatarbelakangi pengecualian ternyata sudah diperbaiki (mis. lewat issue
    lanjutan yang disebut di alasannya) tanpa melepas entrinya di sini, test ini
    GAGAL sebagai pengingat untuk melepas pengecualian tersebut.
    """
    documents = _extract_graphql_documents(_TOOLS_DIR / f"{module_name}.py")
    assert documents
    assert not _all_documents_valid(wikijs_schema, documents), (
        f"modul {module_name!r} terdaftar di _KNOWN_INVALID_MODULES tapi seluruh "
        "dokumennya kini valid terhadap SDL -- lepas entri pengecualian ini "
        "(temuan yang melatarbelakanginya kemungkinan sudah diperbaiki)."
    )


def test_stale_exception_entry_is_rejected(wikijs_schema: GraphQLSchema) -> None:
    """Negatif: membuktikan mekanisme anti-basi benar-benar menangkap pengecualian basi.

    Modul ``groups`` diketahui lolos validasi penuh (``andhit-r/wikijs-mcp#4``).
    Memperlakukannya seolah masuk :data:`_KNOWN_INVALID_MODULES` harus membuat
    pengecekan anti-basi (:func:`_all_documents_valid`) mengembalikan ``True``,
    persis skenario yang seharusnya digagalkan
    :func:`test_known_invalid_module_not_stale`.
    """
    documents = _extract_graphql_documents(_TOOLS_DIR / "groups.py")
    assert documents
    assert _all_documents_valid(wikijs_schema, documents), (
        "modul 'groups' seharusnya lolos penuh -- bila assert ini gagal, "
        "mekanisme anti-basi test_known_invalid_module_not_stale tidak lagi "
        "punya baseline modul valid yang bisa dijadikan bukti bahwa pengecekan "
        "itu benar-benar mendeteksi pengecualian basi."
    )


def test_module_without_documents_fails_gate(tmp_path: Path) -> None:
    """Negatif: modul sintetis tanpa literal ``query``/``mutation`` gagal, bukan lolos diam-diam.

    Membuktikan :func:`_extract_graphql_documents` mengembalikan daftar kosong
    untuk modul yang tidak memakai pola literal ``query``/``mutation`` sama
    sekali, dan bahwa gate (:func:`test_module_has_extracted_documents`)
    menolaknya lewat ``assert documents`` — bukan lolos diam-diam dengan nol
    dokumen tervalidasi.
    """
    empty_module = tmp_path / "empty_tool.py"
    empty_module.write_text(
        "def register(mcp, client):\n    pass\n",
        encoding="utf-8",
    )
    documents = _extract_graphql_documents(empty_module)
    assert documents == []
    with pytest.raises(AssertionError):
        assert documents, "modul 'empty_tool' menghasilkan nol dokumen GraphQL terekstrak"


def test_validator_rejects_unknown_field(wikijs_schema: GraphQLSchema) -> None:
    """Negatif: dokumen sintetis yang menyeleksi field karangan ditolak validator.

    Membuktikan gate ini benar-benar menangkap ketidakcocokan skema (kelas bug
    asli ``andhit-r/wikijs-mcp#4``: ``userCount`` pada tipe ``Group``), bukan
    validator yang selalu hijau apa pun isi dokumennya.
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


def test_validator_rejects_nullable_variable_for_nonnull_argument(
    wikijs_schema: GraphQLSchema,
) -> None:
    """Negatif: variabel nullable dipakai di posisi argumen non-null ditolak validator.

    Kelas bug persis ``groups.update`` (``andhit-r/wikijs-mcp#4``): argumen
    Wiki.js sungguhan non-null (di sini ``UserMutation.delete.replaceId: Int!``,
    lihat catatan :data:`_KNOWN_INVALID_MODULES`) tapi dokumen mendeklarasikan
    variabelnya sebagai nullable tanpa default.
    """
    bad_document = """
    mutation($replaceId: Int) {
      users {
        delete(id: 1, replaceId: $replaceId) {
          responseResult { succeeded }
        }
      }
    }
    """
    errors = validate(wikijs_schema, parse(bad_document))
    assert errors, "validator seharusnya menolak variabel nullable pada argumen non-null"
