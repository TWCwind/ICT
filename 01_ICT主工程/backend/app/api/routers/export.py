from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.ids import new_id
from app.repo import get_resource_item, insert_learning_event
from app.schemas import ApiResponse, ExportPackageRequest


router = APIRouter(prefix="/api/export", tags=["export"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    f'<Override PartName="/word/document.xml" ContentType="{DOCX_MEDIA_TYPE}.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)

_DOCUMENT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
    'Target="styles.xml"/>'
    "</Relationships>"
)

_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f"<w:styles {_W_NS}>"
    "<w:docDefaults><w:rPrDefault><w:rPr>"
    '<w:rFonts w:ascii="Calibri" w:eastAsia="Microsoft YaHei" w:hAnsi="Calibri"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/>'
    "</w:rPr></w:rPrDefault>"
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    "</w:docDefaults>"
    '<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="320" w:after="160"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>'
    "</w:styles>"
)


class ExportWordRequest(BaseModel):
    title: str = "导出文档"
    content: str = ""
    file_name: str = ""
    template: str = ""


class ExportImageRequest(BaseModel):
    image_url: str = Field(min_length=1)
    title: str = "生成图片"
    file_name: str = "生成图片.png"
    headers: dict[str, str] = Field(default_factory=dict)


def _resolve_local_image(image_url: str) -> Path:
    parsed = urlsplit(image_url.strip())
    url_path = unquote(parsed.path or "")
    if not url_path.startswith("/files/"):
        raise HTTPException(status_code=400, detail="仅支持导出本系统已经保存的图片")

    files_root = settings.files_path.resolve()
    candidate = (files_root / url_path.removeprefix("/files/")).resolve()
    try:
        candidate.relative_to(files_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="图片地址不合法") from exc

    if candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        raise HTTPException(status_code=400, detail="目标文件不是可导出的图片")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在或已被清理")
    return candidate


@router.post("/image")
async def export_image(req: ExportImageRequest) -> FileResponse:
    image_path = _resolve_local_image(req.image_url)
    requested_name = Path(req.file_name or "").name.strip()
    download_name = requested_name or f"{(req.title or '生成图片').strip()}{image_path.suffix.lower()}"
    if Path(download_name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        download_name = f"{Path(download_name).stem or '生成图片'}{image_path.suffix.lower()}"
    return FileResponse(image_path, filename=download_name, media_type=f"image/{image_path.suffix.lower().lstrip('.').replace('jpg', 'jpeg')}")


@router.post("/package", response_model=ApiResponse)
async def export_package(req: ExportPackageRequest) -> ApiResponse:
    request_id = new_id()
    export_dir = settings.data_path / "exports" / req.student_id
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{new_id()}.zip"
    zip_path = export_dir / zip_name

    resource_ids = req.resource_ids
    if not resource_ids:
        return ApiResponse(
            request_id=request_id,
            success=False,
            error={"code": "EXPORT_EMPTY", "message": "resource_ids 为空"},
        )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rid in resource_ids:
            item = get_resource_item(rid)
            if not item:
                continue
            file_path = settings.data_path / Path(item["content_uri"])
            if file_path.exists():
                arcname = f"{item['type']}-{item['title']}-{rid}{file_path.suffix}"
                zf.write(file_path, arcname=arcname)

    insert_learning_event(req.student_id, "export", {"zip": str(zip_path)})
    return ApiResponse(
        request_id=request_id,
        success=True,
        data={"download_url": f"/exports/{req.student_id}/{zip_name}", "file_name": zip_name},
    )


def _xml_text(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def _docx_paragraph(text: str, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return (
        "<w:p>"
        f"{ppr}"
        '<w:r><w:t xml:space="preserve">'
        f"{_xml_text(text)}"
        "</w:t></w:r>"
        "</w:p>"
    )


_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE = re.compile(r"`([^`]+)`")


def _markdown_to_docx_body(content: str) -> str:
    """把纯文本/Markdown 正文转成 WordprocessingML 段落序列（不依赖 python-docx）。"""
    parts: list[str] = []
    for raw_line in (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            parts.append("<w:p/>")
            continue
        if line.startswith("```"):
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            style = {1: "Heading1", 2: "Heading2"}.get(level, "Heading3")
            parts.append(_docx_paragraph(heading.group(2).strip(), style))
            continue
        bullet = re.match(r"^[-*+]\s+(.*)$", line)
        if bullet:
            parts.append(_docx_paragraph("• " + bullet.group(1).strip()))
            continue
        numbered = re.match(r"^(\d+)[.、)]\s*(.*)$", line)
        if numbered:
            parts.append(_docx_paragraph(f"{numbered.group(1)}. {numbered.group(2).strip()}"))
            continue
        clean = _INLINE_BOLD.sub(r"\1", line)
        clean = _INLINE_CODE.sub(r"\1", clean)
        parts.append(_docx_paragraph(clean))
    return "".join(parts) or "<w:p/>"


def _build_docx(title: str, body_xml: str) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {_W_NS}><w:body>"
        f"{_docx_paragraph(title, 'Heading1')}"
        f"{body_xml}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", _STYLES)
    return buffer.getvalue()


def _safe_file_name(name: str, fallback: str) -> str:
    candidate = Path(name or "").name.strip()
    candidate = re.sub(r'[\\/:*?"<>|\r\n]+', "_", candidate).strip(" ._")
    if not candidate:
        candidate = re.sub(r'[\\/:*?"<>|\r\n]+', "_", fallback).strip(" ._") or "导出文档"
    if not candidate.lower().endswith(".docx"):
        candidate = f"{Path(candidate).stem or '导出文档'}.docx"
    return candidate


@router.post("/word")
async def export_word(req: ExportWordRequest) -> Response:
    title = (req.title or "导出文档").strip() or "导出文档"
    body_xml = _markdown_to_docx_body(req.content)
    payload = _build_docx(title, body_xml)
    file_name = _safe_file_name(req.file_name, title)
    encoded = quote(file_name)
    headers = {"Content-Disposition": f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"}
    return Response(content=payload, media_type=DOCX_MEDIA_TYPE, headers=headers)

