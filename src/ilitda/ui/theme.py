"""화면 공통 스타일.

색·간격·모서리 값은 .streamlit/config.toml의 테마와 같은 값을 쓴다.
Streamlit이 만든 임의 클래스에 의존하지 않고, 우리가 key를 준 컨테이너(st-key-*)와
우리가 직접 그린 HTML의 클래스(il-*)만 꾸민다. data-testid는 Streamlit이 공식으로 유지하는 식별자다.
"""
import streamlit as st

TOKENS = {
    "bg": "#F6F7F9", "surface": "#FFFFFF", "text": "#172B2A", "muted": "#5B6B69",
    "accent": "#167D68", "accent_soft": "#E6F2EF", "accent_line": "#BFE0D7", "border": "#E2E7E5",
    "warn": "#9A5B00", "warn_soft": "#FFF4E0", "danger": "#B42318", "danger_soft": "#FDECEA",
    "info": "#1F4FB0", "info_soft": "#E9EFFB", "gray_soft": "#EEF1F0",
}

CSS = """
<style>
:root {
  --il-bg: {bg}; --il-surface: {surface}; --il-text: {text}; --il-muted: {muted};
  --il-accent: {accent}; --il-accent-soft: {accent_soft}; --il-accent-line: {accent_line}; --il-border: {border};
  --il-warn: {warn}; --il-warn-soft: {warn_soft}; --il-danger: {danger}; --il-danger-soft: {danger_soft};
  --il-info: {info}; --il-info-soft: {info_soft}; --il-gray-soft: {gray_soft};
  --il-radius: 12px; --il-radius-sm: 8px;
}
/* 본문 폭·여백 */
[data-testid="stMainBlockContainer"] { padding-top: 4rem; padding-bottom: 4rem; max-width: 1240px; }
[data-testid="stSidebar"] { border-right: 1px solid var(--il-border); }
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 0.75rem; }
[data-testid="stSidebarHeader"] { padding-bottom: 0; }
h1, h2, h3 { letter-spacing: -0.01em; }
p, li { line-height: 1.6; }

/* 표면(카드) — key가 card-로 시작하는 컨테이너 */
[class*="st-key-card-"] {
  background: var(--il-surface); border: 1px solid var(--il-border); border-radius: var(--il-radius);
  padding: 16px 18px; box-shadow: 0 1px 2px rgba(23, 43, 42, 0.04);
}
[class*="st-key-card-"] [data-testid="stHeadingWithActionElements"] h2,
[class*="st-key-card-"] [data-testid="stHeadingWithActionElements"] h3 { margin-top: 0; padding-top: 0; }
/* 상단 띠: 업무명·진행 단계·주 행동 */
[class~="st-key-pagehead"] {
  background: var(--il-surface); border: 1px solid var(--il-border); border-radius: var(--il-radius);
  padding: 18px 20px 14px; margin-bottom: 4px;
}
/* 실제용 업로드 영역: 큰 점선 드롭존 (Dropbox·Google Drive·Notion 가져오기 화면과 같은 구성) */
.st-key-start-drop [data-testid="stFileUploaderDropzone"] {
  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
  min-height: 240px; padding: 28px 24px; gap: 6px;
  border: 2px dashed var(--il-accent-line); border-radius: 14px; background: #FBFCFC;
  transition: border-color .15s, background .15s;
}
.st-key-start-drop [data-testid="stFileUploaderDropzone"]:hover,
.st-key-start-drop [data-testid="stFileUploaderDropzone"]:focus-within { border-color: var(--il-accent); background: var(--il-accent-soft); }
.st-key-start-drop [data-testid="stFileUploaderDropzone"]::before {
  content: "cloud_upload"; font-family: "Material Symbols Rounded"; font-size: 44px; line-height: 1; color: var(--il-accent);
  order: 0; margin-bottom: 8px;
}
.st-key-start-drop [data-testid="stFileUploaderDropzone"]::after {
  content: "Upload or drag your files here"; order: 1; font-size: 18px; font-weight: 700; color: var(--il-text); letter-spacing: -0.01em;
}
.st-key-start-drop [data-testid="stFileUploaderDropzoneInstructions"] { order: 2; margin: 0; }
.st-key-start-drop [data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 0; color: var(--il-muted); }
.st-key-start-drop [data-testid="stFileUploaderDropzoneInstructions"] span::after { font-size: 13px; }
.st-key-start-drop [data-testid="stFileUploaderDropzone"] > span { order: 3; margin-top: 14px; }
.st-key-start-drop [data-testid="stFileUploaderDropzone"] button { border-radius: 8px; padding: 6px 16px; border-color: var(--il-accent); color: var(--il-accent); background: var(--il-surface); }
.st-key-start-drop [data-testid="stFileUploaderDropzone"] button p { font-size: 0; }
.st-key-start-drop [data-testid="stFileUploaderDropzone"] button p::after { content: "파일 찾기"; font-size: 14px; font-weight: 600; }
.st-key-start-drop [data-testid="stFileUploaderDropzone"] button [data-testid="stIconMaterial"] { display: none; }
.st-key-start-actions { border-top: 1px solid var(--il-border); padding-top: 14px; margin-top: 6px; }
/* 사이드바 메뉴 버튼은 왼쪽 정렬 */
/* 사이드바 메뉴: Linear·Notion식 — 왼쪽 정렬, 낮은 행, 현재 항목은 옅은 강조색 배경 */
[class*="st-key-nav-"] { margin-bottom: -6px; }
[class*="st-key-nav-"] button { justify-content: flex-start; text-align: left; min-height: 36px; padding: 4px 10px; border-radius: 8px; border: none; font-weight: 500; }
[class*="st-key-nav-"] button > div { justify-content: flex-start; width: 100%; gap: 10px; }
[class*="st-key-nav-"] button p { text-align: left; font-size: 14px; }
[class*="st-key-nav-"] button[kind="tertiary"] { color: var(--il-text); }
[class*="st-key-nav-"] button[kind="tertiary"]:hover { background: var(--il-bg); color: var(--il-text); }
[class*="st-key-nav-"] button[kind="tertiary"] [data-testid="stIconMaterial"] { color: var(--il-muted); }
[class*="st-key-nav-"] button[kind="primary"] { background: var(--il-accent-soft); color: var(--il-accent); font-weight: 600; box-shadow: none; }
[class*="st-key-nav-"] button[kind="primary"]:hover { background: var(--il-accent-soft); color: var(--il-accent); }
[class*="st-key-nav-"] button[kind="primary"] [data-testid="stIconMaterial"] { color: var(--il-accent); }
[data-testid="stSidebar"] hr { margin: 10px 0 12px; }
.il-side-label { font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--il-muted); margin: 2px 0 6px; }
/* 오른쪽 근거 패널은 스크롤해도 따라온다 (넓은 화면) */
@media (min-width: 900px) { [class*="st-key-card-evidence"] { position: sticky; top: 3.5rem; } }

/* 직접 그린 HTML */
.il-brand { padding: 2px 4px 14px; }
.il-brand .name { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; color: var(--il-text); line-height: 1.2; }
.il-brand small { display: block; font-size: 12px; color: var(--il-muted); font-weight: 500; line-height: 1.45; margin-top: 8px; }
.il-title { font-size: 24px; font-weight: 650; letter-spacing: -0.02em; line-height: 1.3; margin: 0; overflow-wrap: anywhere; word-break: keep-all; color: var(--il-text); }
.il-sub { color: var(--il-muted); font-size: 14px; margin-top: 4px; margin-bottom: 14px; line-height: 1.5; overflow-wrap: anywhere; }
.il-lead { font-size: 15px; color: var(--il-text); margin: 8px 0 2px; line-height: 1.55; overflow-wrap: anywhere; }
.il-stepper { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 6px; }
.il-step { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; padding: 4px 10px 4px 6px; border-radius: 999px;
  border: 1px solid var(--il-border); color: var(--il-muted); background: var(--il-surface); white-space: nowrap; }
.il-step .n { display: inline-flex; width: 18px; height: 18px; border-radius: 50%; align-items: center; justify-content: center;
  font-size: 11px; border: 1px solid currentColor; }
.il-step.done { color: var(--il-accent); border-color: var(--il-accent-line); background: var(--il-accent-soft); }
.il-step.done .n { background: var(--il-accent); color: #fff; border-color: var(--il-accent); }
.il-step.current { color: #fff; background: var(--il-accent); border-color: var(--il-accent); font-weight: 600; }
.il-step.current .n { border-color: rgba(255,255,255,.7); }
.il-step.blocked { color: var(--il-danger); border-color: #F3C9C4; background: var(--il-danger-soft); }
.il-kv { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 14px; color: var(--il-muted); margin-top: 10px; }
.il-kv b { color: var(--il-text); font-weight: 600; overflow-wrap: anywhere; }
.il-chip { display: inline-block; font-size: 12px; line-height: 1.5; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--il-border);
  background: var(--il-surface); color: var(--il-muted); margin-right: 4px; white-space: nowrap; vertical-align: middle; }
.il-chip.ok { color: var(--il-accent); background: var(--il-accent-soft); border-color: var(--il-accent-line); }
.il-chip.warn { color: var(--il-warn); background: var(--il-warn-soft); border-color: #F2D9A6; }
.il-chip.danger { color: var(--il-danger); background: var(--il-danger-soft); border-color: #F3C9C4; }
.il-chip.info { color: var(--il-info); background: var(--il-info-soft); border-color: #C9D6F4; }
.il-chip.gray { color: var(--il-muted); background: var(--il-gray-soft); }
.il-row { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-top: 1px solid var(--il-border); }
.il-row.first { border-top: 0; padding-top: 2px; }
.il-num { flex: 0 0 28px; height: 28px; border-radius: var(--il-radius-sm); background: var(--il-accent-soft); color: var(--il-accent);
  font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 13px; margin-top: 1px; }
.il-num.warn { background: var(--il-warn-soft); color: var(--il-warn); }
.il-num.gray { background: var(--il-gray-soft); color: var(--il-muted); }
.il-body { flex: 1 1 auto; min-width: 0; }
.il-main { font-size: 15px; font-weight: 600; color: var(--il-text); overflow-wrap: anywhere; word-break: keep-all; line-height: 1.5; }
.il-meta { font-size: 13px; color: var(--il-muted); margin-top: 3px; overflow-wrap: anywhere; line-height: 1.5; }
.il-meta b { color: var(--il-text); font-weight: 600; }
.il-ev { border-left: 3px solid var(--il-border); padding: 6px 12px; margin: 8px 0; font-size: 14px; }
.il-ev.ok { border-left-color: var(--il-accent-line); }
.il-ev.bad { border-left-color: #F3C9C4; }
.il-ev .doc { font-weight: 600; color: var(--il-text); overflow-wrap: anywhere; }
.il-ev q { display: block; quotes: "“" "”"; color: var(--il-text); margin: 2px 0; overflow-wrap: anywhere; }
.il-ev .loc { color: var(--il-muted); font-size: 13px; }
.il-src { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; background: var(--il-bg); border: 1px solid var(--il-border);
  border-radius: var(--il-radius-sm); padding: 8px 10px; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--il-text); margin: 4px 0 2px; }
.il-src .hit { background: #FFF1B8; }
.il-empty { border: 1px dashed var(--il-border); border-radius: var(--il-radius); padding: 22px 20px; text-align: left; background: var(--il-surface); }
.il-empty .t { font-size: 16px; font-weight: 600; color: var(--il-text); }
.il-empty .b { font-size: 14px; color: var(--il-muted); margin-top: 4px; line-height: 1.55; }
.il-note { border-radius: var(--il-radius-sm); padding: 10px 12px; font-size: 14px; line-height: 1.55; border: 1px solid var(--il-border); background: var(--il-surface); overflow-wrap: anywhere; }
.il-note.warn { border-color: #F2D9A6; background: var(--il-warn-soft); color: var(--il-warn); }
.il-note.danger { border-color: #F3C9C4; background: var(--il-danger-soft); color: var(--il-danger); }
.il-note.ok { border-color: var(--il-accent-line); background: var(--il-accent-soft); color: var(--il-accent); }
.il-note.info { border-color: #C9D6F4; background: var(--il-info-soft); color: var(--il-info); }
.il-note .t { font-weight: 700; display: block; }
.il-diff { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px; }
.il-diff > div { border: 1px solid var(--il-border); border-radius: var(--il-radius-sm); padding: 8px 10px; font-size: 13.5px; overflow-wrap: anywhere; background: var(--il-bg); }
.il-diff .lab { font-size: 12px; color: var(--il-muted); display: block; margin-bottom: 2px; }
.il-diff .old { text-decoration: line-through; color: var(--il-muted); }
.il-live { display: flex; gap: 8px; align-items: baseline; font-size: 13.5px; padding: 3px 0; border-top: 1px dashed var(--il-border); }
.il-live:first-child { border-top: 0; }
.il-live .t { color: var(--il-text); font-weight: 500; overflow-wrap: anywhere; }
.il-live .d { color: var(--il-muted); font-size: 12.5px; overflow-wrap: anywhere; }
.il-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.il-sec h3 { margin: 0; font-size: 17px; font-weight: 650; }
.il-sec .r { font-size: 13px; color: var(--il-muted); }
.il-small { font-size: 13px; color: var(--il-muted); line-height: 1.55; }
.il-wrap { overflow-wrap: anywhere; word-break: keep-all; }
@media (max-width: 640px) {
  .il-title { font-size: 21px; }
  [class*="st-key-card-"] { padding: 12px 14px; }
  [class~="st-key-pagehead"] { padding: 14px 14px 10px; }
  .il-diff { grid-template-columns: 1fr; }
  .il-step { font-size: 12px; }
}
</style>
"""


def inject():
    """매 실행마다 스타일을 넣는다. 가볍고, 다시 그려도 상태를 바꾸지 않는다."""
    css = CSS
    for name, value in TOKENS.items():
        css = css.replace("{" + name + "}", value)
    st.html(css)
