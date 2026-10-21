"""Flusso completo via API con agente e trascrizione simulati (FFmpeg e Chrome reali)."""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="rs-e2e-"))
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ["PUBLIC_BASE_URL"] = "https://tunnel.example.com"
os.environ["IG_APP_SECRET"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import workflows  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.social import dm, instagram  # noqa: E402

WORDS = "oggi ti spiego tre errori che tutti fanno con il design delle landing page".split()


def fake_transcribe(audio, duration, on_progress=None):
    return {"language": "it", "segments": [{"s": 0, "e": 5.5, "text": " ".join(WORDS)}],
            "words": [{"w": w, "s": round(i * 0.4, 2), "e": round(i * 0.4 + 0.35, 2)} for i, w in enumerate(WORDS)]}


def fake_agent(system, prompt):
    if "Self-Learning" in system:
        return '```json\n{"summary": "Sottotitoli più in alto", "changes": [{"path": "captions/rules.md", ' \
               '"reason": "feedback ripetuto", "content": "# Sottotitoli\\n- position_y 0.60"}]}\n```'
    if "content strategist" in system:
        return json.dumps({"title": "Errori di design", "keyword": "design", "caption": "3 errori... Commenta DESIGN",
                           "hashtags": "#design", "dm_message": "Ecco la guida",
                           "lead_magnet": {"type": "Checklist", "title": "Landing page senza errori",
                                           "subtitle": "La checklist", "intro": "Intro",
                                           "sections": [{"heading": "Gerarchia", "items": ["Un solo titolo"]}],
                                           "closing": "Seguimi"}})
    asset_id = int(prompt.split("### Asset video ")[1].split(" ")[0])
    if "Revisione montaggio" in prompt:
        return json.dumps({"clips": [{"id": "c1", "source": asset_id, "in": 0.0, "out": 2.0}],
                           "captions": {"position_y": 0.6}, "_note": "Sottotitoli alzati"})
    return f'```json\n{{"clips": [{{"id": "c1", "source": {asset_id}, "in": 0.0, "out": 2.5}}, ' \
           f'{{"id": "c2", "source": {asset_id}, "in": 3.0, "out": 4.5, "transition_in": "fade"}}]}}\n```'


@pytest.fixture(scope="module")
def client():
    skills_copy = TMP / "skills"
    shutil.copytree(Path(__file__).resolve().parents[2] / "skills", skills_copy)
    settings.skills_dir = skills_copy
    workflows.transcribe = fake_transcribe
    workflows.runner._claude_cli = fake_agent
    workflows.runner.PROVIDERS["claude-cli"] = fake_agent
    with TestClient(app, base_url="http://localhost") as c:
        yield c


def wait_job(c, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        jobs = c.get("/api/system").json()["jobs"]
        job = next(j for j in jobs if j["id"] == job_id)
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.3)
    raise TimeoutError(job_id)


@pytest.fixture(scope="module")
def video():
    path = TMP / "clip.mov"
    subprocess.run([settings.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=6", "-shortest", "-c:v", "libx264", "-c:a", "aac",
                    str(path)], check=True)
    return path


def test_full_flow(client, video):
    c = client
    p = c.post("/api/projects", json={"name": "Errori design", "script": "hook, 3 errori, CTA"}).json()
    pid = p["id"]

    with video.open("rb") as f:
        up = c.post(f"/api/projects/{pid}/assets", files=[("files", ("clip.mov", f, "video/quicktime"))])
    assert up.status_code == 200, up.text
    assert up.json()[0]["thumb_url"]

    job = c.post(f"/api/projects/{pid}/process").json()
    done = wait_job(c, job["id"])
    assert done["status"] == "done", done
    detail = c.get(f"/api/projects/{pid}").json()
    assert detail["status"] == "ready" and detail["current_version"] == 1
    assert detail["versions"][0]["render_status"] == "done"

    # feedback a timestamp + revisione
    fb = c.post(f"/api/projects/{pid}/feedback", json={"timestamp": 1.2, "text": "Sottotitoli più in alto"})
    assert fb.status_code == 200
    job = c.post(f"/api/projects/{pid}/feedback/apply").json()
    assert wait_job(c, job["id"])["status"] == "done"
    detail = c.get(f"/api/projects/{pid}").json()
    assert detail["current_version"] == 2
    assert detail["versions"][0]["note"] == "Sottotitoli alzati"
    assert detail["feedback"][0]["status"] == "applied"

    # Self-Learning con approvazione
    job = c.post("/api/learning/run").json()
    assert wait_job(c, job["id"])["status"] == "done"
    prop = c.get("/api/learning").json()["proposals"][0]
    assert prop["changes"][0]["before"].startswith("# Sottotitoli")
    assert c.post(f"/api/learning/proposals/{prop['id']}/approve", json={}).status_code == 200
    assert "0.60" in (settings.skills_dir / "captions/rules.md").read_text()
    assert c.get("/api/learning").json()["pending_feedback"] == []

    # contenuti + PDF
    job = c.post(f"/api/projects/{pid}/content/generate").json()
    result = wait_job(c, job["id"])
    assert result["status"] == "done", result
    content = c.get(f"/api/projects/{pid}/content").json()
    assert content["keyword"] == "DESIGN" and Path(content["pdf_path"]).stat().st_size > 1000
    assert content["link"].startswith("https://tunnel.example.com/r/")

    # automazione DM
    auto = c.post("/api/automations", json={"project_id": pid, "keyword": "design"}).json()
    assert auto["dm_message"] == "Ecco la guida"
    sent = []
    instagram_calls = {
        "private_reply": lambda cid, text, *a: sent.append(("private", cid, a)),
        "send_message": lambda igsid, text, *a: sent.append(("dm", igsid, text)),
        "user_profile": lambda igsid: {"username": "mario", "is_user_follow_business": igsid == "U1"},
        "reply_to_comment": lambda *a: None,
    }
    for name, fn in instagram_calls.items():
        setattr(instagram, name, fn)
    dm.get_account = lambda platform: None

    body = {"object": "instagram", "entry": [{"changes": [{"field": "comments", "value": {
        "id": "C1", "text": "Design! 🔥", "from": {"id": "U1", "username": "mario"}, "media": {"id": "M1"}}}]}]}
    assert c.post("/webhooks/instagram", json=body).status_code == 200
    assert sent[0][0] == "private" and sent[0][2][1] == f"RS_AUTO:{auto['id']}"
    # stesso commento consegnato due volte → ignorato
    c.post("/webhooks/instagram", json=body)
    assert len(sent) == 1

    msg = {"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "U1"}, "recipient": {"id": "ME"},
            "message": {"mid": "m1", "text": "Inviamela", "quick_reply": {"payload": f"RS_AUTO:{auto['id']}"}}}]}]}
    c.post("/webhooks/instagram", json=msg)
    assert sent[-1][0] == "dm" and "tunnel.example.com/r/" in sent[-1][2]
    leads = c.get("/api/leads").json()
    assert leads[0]["status"] == "sent"

    # utente che non segue la pagina
    body["entry"][0]["changes"][0]["value"].update({"id": "C2", "from": {"id": "U2", "username": "anna"}})
    c.post("/webhooks/instagram", json=body)
    msg["entry"][0]["messaging"][0]["sender"]["id"] = "U2"
    c.post("/webhooks/instagram", json=msg)
    assert c.get("/api/leads").json()[0]["status"] == "awaiting_follow"

    # pagina pubblica della risorsa
    slug = content["slug"]
    page = c.get(f"/r/{slug}", headers={"host": "tunnel.example.com"})
    assert page.status_code == 200 and "Landing page senza errori" in page.text


def test_tunnel_guard(client):
    assert client.get("/api/projects", headers={"host": "tunnel.example.com"}).status_code == 404
    assert client.get("/api/projects").status_code == 200
    r = client.get("/webhooks/instagram", params={"hub.mode": "subscribe", "hub.verify_token": "reel-studio",
                                                  "hub.challenge": "42"}, headers={"host": "tunnel.example.com"})
    assert r.text == "42"


def test_keyword_matching():
    assert dm.matches("DESIGN", "voglio la guida design!!")
    assert dm.matches("CAFFE", "Caffè per favore")
    assert not dm.matches("DESIGN", "designer")
