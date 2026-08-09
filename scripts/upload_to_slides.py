#!/usr/bin/env python3
"""Upload slide materials from upload.json to Google Slides via Slides API + Drive API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

# Google Slides page size for 16:9 (10" x 5.625")
PAGE_WIDTH_EMU = 9144000
PAGE_HEIGHT_EMU = 5143500

LAYOUT_PRESENTATION = "TITLE_AND_BODY"
LAYOUT_MANGA = "BLANK"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Google Slides from output/{slug}/upload.json"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Path to output folder containing upload.json and images/",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("secrets/getstockdata05-service-account.json"),
        help="Service account JSON key path",
    )
    parser.add_argument(
        "--share-with",
        type=str,
        default=None,
        help="Gmail address to share the presentation with (writer)",
    )
    parser.add_argument(
        "--presentation-id",
        type=str,
        default=None,
        help=(
            "Existing presentation ID or Google Slides URL. "
            "Use when the service account cannot create new files "
            "(share the deck with the SA as Editor first)."
        ),
    )
    parser.add_argument(
        "--image-folder-id",
        type=str,
        default=None,
        help=(
            "Drive folder ID (or folder URL) that already contains slide images. "
            "Share the folder with the service account (Viewer+). "
            "Defaults to config/drive_staging.json when omitted."
        ),
    )
    parser.add_argument(
        "--prepend",
        action="store_true",
        help=(
            "LEGACY/emergency only: insert thumbnail slide(s) at the start of an "
            "existing deck. New videos should include thumbnail in upload.json "
            "and do a full upload (do not use --prepend as the normal path)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate upload.json without calling Google APIs",
    )
    return parser.parse_args()


def resolve_presentation_id(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    marker = "/presentation/d/"
    if marker in value:
        rest = value.split(marker, 1)[1]
        return rest.split("/", 1)[0].split("?", 1)[0]
    return value


def resolve_drive_folder_id(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    # https://drive.google.com/drive/folders/FOLDER_ID
    marker = "/folders/"
    if marker in value:
        rest = value.split(marker, 1)[1]
        return rest.split("/", 1)[0].split("?", 1)[0]
    return value


def load_default_image_folder_id() -> str | None:
    """Read staging folder id from config/drive_staging.json if present."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "drive_staging.json"
    if not config_path.exists():
        return None
    try:
        with config_path.open(encoding="utf-8") as f:
            data = json.load(f)
        return resolve_drive_folder_id(data.get("image_folder_id") or data.get("image_folder_url"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def load_upload_data(output_dir: Path) -> dict:
    upload_path = output_dir / "upload.json"
    if not upload_path.exists():
        raise FileNotFoundError(f"upload.json not found: {upload_path}")

    with upload_path.open(encoding="utf-8") as f:
        data = json.load(f)

    if data.get("version") != 1:
        raise ValueError("upload.json version must be 1")

    format_type = data.get("format")
    if format_type not in ("presentation", "manga"):
        raise ValueError("format must be 'presentation' or 'manga'")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise ValueError("slides must be a non-empty array")

    for slide in slides:
        image_rel = slide.get("image")
        if not image_rel:
            raise ValueError(f"slide {slide.get('index')} missing image path")
        image_path = output_dir / image_rel
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

    return data


def build_services(credentials_path: Path):
    creds = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=SCOPES,
    )
    slides = build("slides", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return slides, drive


def find_placeholder(page: dict, placeholder_type: str) -> str | None:
    for element in page.get("pageElements", []):
        shape = element.get("shape", {})
        placeholder = shape.get("placeholder", {})
        if placeholder.get("type") == placeholder_type:
            return element["objectId"]
    return None


def get_page_by_object_id(presentation: dict, page_object_id: str) -> dict | None:
    for page in presentation.get("slides", []):
        if page.get("objectId") == page_object_id:
            return page
    return None


def upload_image_to_drive(drive, image_path: Path) -> str:
    media = MediaFileUpload(str(image_path), mimetype="image/png", resumable=True)
    file_metadata = {"name": image_path.name}
    created = (
        drive.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    file_id = created["id"]

    # Temporary public read so Slides API can fetch the image URL.
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return file_id


def list_images_in_folder(drive, folder_id: str) -> dict[str, str]:
    """Return mapping of filename -> Drive file id for files in folder."""
    mapping: dict[str, str] = {}
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    while True:
        resp = (
            drive.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=100,
            )
            .execute()
        )
        for f in resp.get("files", []):
            mapping[f["name"]] = f["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return mapping


def ensure_anyone_reader(drive, file_id: str) -> None:
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def remove_public_permission(drive, file_id: str) -> None:
    try:
        drive.permissions().delete(
            fileId=file_id,
            permissionId="anyoneWithLink",
        ).execute()
    except HttpError:
        pass


def image_url_for_drive_file(file_id: str) -> str:
    return f"https://drive.google.com/thumbnail?sz=w2000&id={file_id}"


def create_slide_requests(
    slide_data: dict,
    page: dict,
    format_type: str,
    image_url: str,
    slide_object_id: str,
) -> list[dict]:
    requests: list[dict] = []

    if format_type == "presentation" and slide_data.get("slide_type") != "thumbnail":
        title_id = find_placeholder(page, "TITLE")
        body_id = find_placeholder(page, "BODY")

        title = slide_data.get("title", "")
        bullets = slide_data.get("bullets", [])
        body_text = "\n".join(f"• {item}" for item in bullets)

        if title_id and title:
            requests.append(
                {
                    "insertText": {
                        "objectId": title_id,
                        "text": title,
                        "insertionIndex": 0,
                    }
                }
            )

        if body_id and body_text:
            requests.append(
                {
                    "insertText": {
                        "objectId": body_id,
                        "text": body_text,
                        "insertionIndex": 0,
                    }
                }
            )

        image_width = int(PAGE_WIDTH_EMU * 0.42)
        image_height = int(PAGE_HEIGHT_EMU * 0.55)
        translate_x = int(PAGE_WIDTH_EMU * 0.53)
        translate_y = int(PAGE_HEIGHT_EMU * 0.22)

        requests.append(
            {
                "createImage": {
                    "url": image_url,
                    "elementProperties": {
                        "pageObjectId": slide_object_id,
                        "size": {
                            "width": {"magnitude": image_width, "unit": "EMU"},
                            "height": {"magnitude": image_height, "unit": "EMU"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": translate_x,
                            "translateY": translate_y,
                            "unit": "EMU",
                        },
                    },
                }
            }
        )
    else:
        # manga + thumbnail: full-bleed image
        requests.append(
            {
                "createImage": {
                    "url": image_url,
                    "elementProperties": {
                        "pageObjectId": slide_object_id,
                        "size": {
                            "width": {"magnitude": PAGE_WIDTH_EMU, "unit": "EMU"},
                            "height": {"magnitude": PAGE_HEIGHT_EMU, "unit": "EMU"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": 0,
                            "translateY": 0,
                            "unit": "EMU",
                        },
                    },
                }
            }
        )

    narration = slide_data.get("narration", "")
    notes_page = page.get("slideProperties", {}).get("notesPage", {})
    speaker_notes_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")

    if narration and speaker_notes_id:
        requests.append(
            {
                "insertText": {
                    "objectId": speaker_notes_id,
                    "text": narration,
                    "insertionIndex": 0,
                }
            }
        )

    return requests


def share_presentation(drive, presentation_id: str, email: str) -> None:
    drive.permissions().create(
        fileId=presentation_id,
        body={"type": "user", "role": "writer", "emailAddress": email},
        sendNotificationEmail=False,
    ).execute()


def upload_to_slides(
    output_dir: Path,
    credentials_path: Path,
    share_with: str | None = None,
    presentation_id: str | None = None,
    image_folder_id: str | None = None,
    prepend: bool = False,
    dry_run: bool = False,
) -> str:
    data = load_upload_data(output_dir)
    title = data.get("title", "YouTube Video Slides")
    format_type = data["format"]
    slides_data = data["slides"]

    if prepend:
        slides_data = [s for s in slides_data if s.get("slide_type") == "thumbnail"]
        if not slides_data:
            raise ValueError("--prepend requires at least one slide with slide_type=thumbnail")
        if not presentation_id:
            raise ValueError("--prepend requires --presentation-id")

    if dry_run:
        print(f"[dry-run] OK: {len(slides_data)} slides, format={format_type}")
        if presentation_id:
            print(f"[dry-run] target presentation_id={presentation_id}")
        if image_folder_id:
            print(f"[dry-run] image_folder_id={image_folder_id}")
        if prepend:
            print("[dry-run] mode=prepend thumbnails only")
        return "dry-run"

    slides_service, drive_service = build_services(credentials_path)

    used_existing = bool(presentation_id)
    folder_image_ids: dict[str, str] = {}
    if image_folder_id:
        folder_image_ids = list_images_in_folder(drive_service, image_folder_id)
        print(f"Found {len(folder_image_ids)} files in image folder")

    if used_existing:
        presentation = (
            slides_service.presentations()
            .get(presentationId=presentation_id)
            .execute()
        )
        if not prepend:
            # Rename to match upload.json title (owner's Drive, so quota is OK).
            drive_service.files().update(
                fileId=presentation_id,
                body={"name": title},
                supportsAllDrives=True,
            ).execute()
    else:
        if prepend:
            raise ValueError("--prepend requires an existing --presentation-id")
        presentation = (
            slides_service.presentations()
            .create(body={"title": title})
            .execute()
        )
        presentation_id = presentation["presentationId"]

    existing_slides = presentation.get("slides", [])
    if not existing_slides:
        raise RuntimeError("Presentation has no slides")

    leftover_ids: list[str] = []
    if not prepend:
        leftover_ids = [s["objectId"] for s in existing_slides]
    uploaded_drive_ids: list[str] = []
    temporary_public_ids: list[str] = []

    for i, slide_data in enumerate(slides_data):
        layout = LAYOUT_PRESENTATION if format_type == "presentation" else LAYOUT_MANGA
        if slide_data.get("slide_type") == "thumbnail":
            layout = LAYOUT_MANGA  # full-bleed title card

        create_slide: dict = {
            "createSlide": {
                "slideLayoutReference": {
                    "predefinedLayout": layout,
                }
            }
        }
        if prepend:
            create_slide["createSlide"]["insertionIndex"] = i

        requests_create: list[dict] = [create_slide]
        # After first new slide exists, delete remaining original blanks (full rebuild only).
        if not prepend and i == 0 and leftover_ids:
            for oid in leftover_ids:
                requests_create.append({"deleteObject": {"objectId": oid}})

        create_resp = (
            slides_service.presentations()
            .batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests_create},
            )
            .execute()
        )
        slide_object_id = create_resp["replies"][0]["createSlide"]["objectId"]
        leftover_ids = []

        presentation = (
            slides_service.presentations()
            .get(presentationId=presentation_id)
            .execute()
        )
        page = get_page_by_object_id(presentation, slide_object_id)
        if page is None:
            raise RuntimeError(f"Failed to find slide page: {slide_object_id}")

        image_path = output_dir / slide_data["image"]
        image_name = Path(slide_data["image"]).name

        if image_folder_id:
            drive_file_id = folder_image_ids.get(image_name)
            if not drive_file_id:
                raise FileNotFoundError(
                    f"Image '{image_name}' not found in Drive folder {image_folder_id}"
                )
            ensure_anyone_reader(drive_service, drive_file_id)
            temporary_public_ids.append(drive_file_id)
        else:
            drive_file_id = upload_image_to_drive(drive_service, image_path)
            uploaded_drive_ids.append(drive_file_id)
            temporary_public_ids.append(drive_file_id)

        image_url = image_url_for_drive_file(drive_file_id)

        requests = create_slide_requests(
            slide_data=slide_data,
            page=page,
            format_type=format_type,
            image_url=image_url,
            slide_object_id=slide_object_id,
        )

        if requests:
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests},
            ).execute()

        print(f"Uploaded slide {i + 1}/{len(slides_data)}: {slide_data.get('title', '')}")
        time.sleep(0.5)

    for file_id in temporary_public_ids:
        remove_public_permission(drive_service, file_id)

    # Only needed when SA created a new deck; existing decks are already owned by the user.
    if share_with and not used_existing:
        share_presentation(drive_service, presentation_id, share_with)

    url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    result_path = output_dir / "slides-result.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "presentation_id": presentation_id,
                "url": url,
                "title": title,
                "slide_count": len(data["slides"]),
                "prepended_thumbnails": len(slides_data) if prepend else 0,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return url


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    credentials_path = args.credentials.resolve()
    presentation_id = resolve_presentation_id(args.presentation_id)
    image_folder_id = resolve_drive_folder_id(args.image_folder_id)
    if not image_folder_id:
        image_folder_id = load_default_image_folder_id()
        if image_folder_id:
            print(f"Using image folder from config/drive_staging.json: {image_folder_id}")

    if not credentials_path.exists():
        print(f"Credentials not found: {credentials_path}", file=sys.stderr)
        return 1

    try:
        url = upload_to_slides(
            output_dir=output_dir,
            credentials_path=credentials_path,
            share_with=args.share_with,
            presentation_id=presentation_id,
            image_folder_id=image_folder_id,
            prepend=args.prepend,
            dry_run=args.dry_run,
        )
        print(f"Done: {url}")
        return 0
    except (FileNotFoundError, ValueError, HttpError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
