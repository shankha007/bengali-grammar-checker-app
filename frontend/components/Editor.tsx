"use client";

import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useCallback, useEffect, useRef } from "react";

import { EditHighlight, editHighlightKey } from "@/lib/EditHighlight";
import { buildDocIndex, spanToRange } from "@/lib/offsets";
import { useLang } from "@/lib/i18n";
import type { Edit, OutOfScopeSpan } from "@/lib/types";

interface Props {
  edits: Edit[];
  outOfScope: OutOfScopeSpan[];
  activeId: string | null;
  onTextChange: (text: string) => void;
  onFlagClick: (editId: string) => void;
  registerApply: (fn: (edit: Edit, replacement: string) => void) => void;
  registerSetText: (fn: (text: string) => void) => void;
}

export default function Editor({
  edits,
  outOfScope,
  activeId,
  onTextChange,
  onFlagClick,
  registerApply,
  registerSetText,
}: Props) {
  const { t } = useLang();
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        // A grammar checker is not a rich-text editor. Every mark the user can
        // apply is another thing that can sit between a flagged span and its
        // decoration, for no benefit to the task.
        heading: false,
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        blockquote: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        horizontalRule: false,
      }),
      EditHighlight.configure({ edits: [], outOfScope: [] }),
    ],
    content: "<p></p>",
    editorProps: {
      attributes: {
        // The editor is the application's main work area.
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": t("editorAria"),
        lang: "bn",
        spellcheck: "false", // ours, not the browser's Latin-trained one
      },
      handleClick(view, pos) {
        const node = view.domAtPos(pos)?.node;
        const el =
          node instanceof HTMLElement ? node : (node?.parentElement ?? null);
        const flag = el?.closest?.("[data-edit-id]") as HTMLElement | null;
        if (flag?.dataset.editId) {
          onFlagClick(flag.dataset.editId);
          return true;
        }
        return false;
      },
    },
    onUpdate({ editor }) {
      onTextChange(buildDocIndex(editor.state.doc).text);
    },
  });

  /** Push new spans into the plugin and force one decoration rebuild. */
  useEffect(() => {
    if (!editor) return;
    const ext = editor.extensionManager.extensions.find(
      (e) => e.name === "editHighlight",
    );
    if (ext) {
      ext.options.edits = edits;
      ext.options.outOfScope = outOfScope;
    }
    editor.view.dispatch(editor.state.tr.setMeta(editHighlightKey, true));
  }, [editor, edits, outOfScope]);

  /** Reflect the active edit in the DOM so hover and keyboard agree. */
  useEffect(() => {
    if (!editor) return;
    const root = editor.view.dom;
    root.querySelectorAll("[data-edit-id]").forEach((el) => {
      const node = el as HTMLElement;
      if (node.dataset.editId === activeId) {
        node.dataset.active = "true";
        node.scrollIntoView({ block: "nearest", behavior: "smooth" });
      } else {
        delete node.dataset.active;
      }
    });
  }, [editor, activeId, edits, outOfScope]);

  const applyEdit = useCallback(
    (edit: Edit, replacement: string) => {
      if (!editor) return;
      const index = buildDocIndex(editor.state.doc);
      const range = spanToRange(index, edit.start, edit.end);
      if (!range) return;
      // insertContentAt goes through the normal transaction path, so it lands in
      // the undo stack and Ctrl+Z reverses it like any other typing.
      editor
        .chain()
        .focus()
        .insertContentAt({ from: range.from, to: range.to }, replacement)
        .run();
    },
    [editor],
  );

  const setText = useCallback(
    (text: string) => {
      if (!editor) return;
      const html = text
        .split("\n")
        .map((line) => `<p>${escapeHtml(line)}</p>`)
        .join("");
      editor.commands.setContent(html || "<p></p>", true);
    },
    [editor],
  );

  useEffect(() => {
    registerApply(applyEdit);
    registerSetText(setText);
  }, [registerApply, applyEdit, registerSetText, setText]);

  return (
    // scroll-y here, not on the page: long documents scroll inside the editor
    // pane so the suggestion table and side panel stay put.
    <div className="bs-editor scroll-y h-full">
      <EditorContent editor={editor} />
    </div>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
