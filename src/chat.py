from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from src.models import Inventory, OrganizationPlan
from src.orchestrator import organize_directory
from src.planner import build_plan
from src.reporter import render_plan_report
from src.scanner import scan_directory
from src.security import resolve_root


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class ChatSession:
    root: Path
    include_dirs: set[str] = field(default_factory=set)
    inventory: Inventory | None = None
    plan: OrganizationPlan | None = None
    report: str | None = None
    history: list[ChatMessage] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "include_dirs": sorted(self.include_dirs),
            "inventory": None if self.inventory is None else self.inventory.to_dict(),
            "plan": None if self.plan is None else self.plan.to_dict(),
            "report": self.report,
            "history": [message.to_dict() for message in self.history],
            "has_inventory": self.inventory is not None,
            "has_plan": self.plan is not None,
            "suggestions": [
                "analizza",
                "piano",
                "mostra",
                "aggiungi directory <cartella>",
                "sposta <source> <destinazione>",
                "review <source>",
            ],
        }


def create_chat_session(root: str | Path) -> ChatSession:
    session = ChatSession(root=resolve_root(root))
    session.history.append(
        ChatMessage(
            role="assistant",
            content=(
                "Chat pronta. Posso analizzare cartelle, rigenerare il piano e riassegnare file con comandi come "
                "'analizza', 'piano', 'aggiungi directory Invoices', 'sposta report.pdf Documents/Reports/finale.pdf'."
            ),
        )
    )
    return session


def execute_chat_command(session: ChatSession, prompt: str) -> dict[str, Any]:
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Inserisci un comando chat.")
    session.history.append(ChatMessage(role="user", content=cleaned))
    if _is_exit(cleaned):
        reply = "Sessione chiusa."
        session.history.append(ChatMessage(role="assistant", content=reply))
        return {"message": reply, "exit": True, "session": session.snapshot()}
    reply = _handle_prompt(session, cleaned)
    session.history.append(ChatMessage(role="assistant", content=reply))
    return {"message": reply, "exit": False, "session": session.snapshot()}


def run_chat(root: str | Path, commands: list[str] | None = None) -> int:
    session = create_chat_session(root)
    scripted = list(commands or [])
    scripted_mode = commands is not None
    print(session.history[0].content)

    while True:
        prompt = scripted.pop(0) if scripted else input("thelibrarian> ").strip()
        if scripted_mode and prompt:
            print(f"> {prompt}")
        if not prompt:
            continue
        try:
            result = execute_chat_command(session, prompt)
            print(result["message"])
            if result["exit"]:
                return 0
        except ValueError as exc:
            print(f"Error: {exc}")


def _handle_prompt(session: ChatSession, prompt: str) -> str:
    lowered = prompt.lower().strip()
    if lowered in {"help", "aiuto", "?"}:
        return (
            "Comandi: scan/analizza, plan/piano, show/mostra, add-dir/aggiungi directory <dir>, "
            "move/sposta <source> <destinazione>, review <source>, reset, exit."
        )
    if lowered == "reset":
        session.include_dirs.clear()
        session.inventory = None
        session.plan = None
        session.report = None
        return "Contesto chat azzerato. Puoi ripartire con 'analizza' o 'piano'."
    if lowered.startswith(("add-dir ", "aggiungi directory ")):
        raw = prompt.split(" ", 1)[1].replace("directory ", "", 1).strip()
        return _add_include_dir(session, raw)
    if lowered in {"scan", "analizza", "analizza cartelle"}:
        inventory = scan_directory(session.root)
        session.inventory = _filter_inventory(inventory, session.include_dirs)
        if session.plan is not None:
            session.plan = build_plan(session.inventory)
            session.report = render_plan_report(session.inventory, session.plan)
        return f"Inventario: {session.inventory.total_files} file in analisi."
    if lowered in {"plan", "piano", "genera piano"}:
        if session.inventory is None:
            inventory = scan_directory(session.root)
            session.inventory = _filter_inventory(inventory, session.include_dirs)
        session.plan = build_plan(session.inventory)
        session.report = render_plan_report(session.inventory, session.plan)
        return (
            f"Piano generato: {len(session.plan.entries)} entry, "
            f"{len(session.plan.review_entries)} in Review, {len(session.plan.warnings)} warning."
        )
    if lowered in {"show", "mostra", "show plan", "mostra piano"}:
        if session.plan is None:
            return "Nessun piano in memoria. Esegui 'piano'."
        return _render_preview(session)
    if lowered.startswith(("move ", "sposta ")):
        if session.plan is None:
            raise ValueError("Esegui prima 'piano'.")
        return _move_entry(session, prompt)
    if lowered.startswith("review "):
        if session.plan is None:
            raise ValueError("Esegui prima 'piano'.")
        source = prompt.split(" ", 1)[1].strip()
        destination = f"Review/{PurePosixPath(source).name}"
        return _rewrite_entry(session, source, destination, "Riassegnato manualmente in chat a Review.", 0.4)
    if lowered in {"run", "esegui"}:
        run = organize_directory(session.root, dry_run=True)
        return f"Dry-run completato: {run.execution.applied_count} operazioni proposte."
    return "Comando non riconosciuto. Usa 'help'."


def _is_exit(prompt: str) -> bool:
    return prompt.lower().strip() in {"exit", "quit", "esci", "q"}


def _add_include_dir(session: ChatSession, raw: str) -> str:
    candidate = (session.root / raw).resolve()
    try:
        relative = candidate.relative_to(session.root).as_posix()
    except ValueError as exc:
        raise ValueError("La directory deve restare sotto la root assegnata.") from exc
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError(f"Directory non trovata: {relative}")
    session.include_dirs.add(relative)
    return f"Aggiunta directory in analisi: {relative}"


def _filter_inventory(inventory: Inventory, include_dirs: set[str]) -> Inventory:
    if not include_dirs:
        return inventory
    prefixes = tuple(f"{item}/" for item in include_dirs)
    filtered = [record for record in inventory.files if record.parent in include_dirs or record.relative_path.startswith(prefixes)]
    warnings = list(inventory.warnings)
    warnings.append(f"Inventory filtrato su {len(include_dirs)} directory esplicite.")
    return Inventory(root=inventory.root, files=filtered, warnings=warnings, scanned_at=inventory.scanned_at)


def _move_entry(session: ChatSession, prompt: str) -> str:
    chunks = prompt.split()
    if len(chunks) < 3:
        raise ValueError("Sintassi: move <source> <destinazione>")
    source = chunks[1]
    destination = " ".join(chunks[2:])
    return _rewrite_entry(session, source, destination, "Riassegnato manualmente via chat.", 0.65)


def _rewrite_entry(session: ChatSession, source: str, destination: str, reason: str, confidence: float) -> str:
    assert session.plan is not None
    normalized_source = PurePosixPath(source).as_posix()
    normalized_destination = PurePosixPath(destination).as_posix()
    for entry in session.plan.entries:
        if entry.source == normalized_source:
            entry.destination = normalized_destination
            entry.reason = reason
            entry.confidence = confidence
            entry.status = "planned"
            entry.warning = None
            session.report = render_plan_report(session.inventory, session.plan) if session.inventory is not None else session.report
            return f"Aggiornato: {normalized_source} -> {normalized_destination}"
    raise ValueError(f"Source non presente nel piano: {normalized_source}")


def _render_preview(session: ChatSession, limit: int = 10) -> str:
    assert session.plan is not None
    rows = []
    for entry in session.plan.entries[:limit]:
        rows.append(f"- {entry.source} -> {entry.destination} ({entry.confidence:.2f})")
    remaining = len(session.plan.entries) - min(len(session.plan.entries), limit)
    if remaining > 0:
        rows.append(f"... altri {remaining} file.")
    return "\n".join(rows)
