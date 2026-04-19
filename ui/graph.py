"""
HorizontalMindMapWidget — horizontal mind-map for FileSense.

Column proportions  20 % | 25 % | 55 %
  Col 0 (20 %): root node, centred vertically. Short-desc below pill.
  Col 1 (25 %): children — each gets H/n vertical slot (25 % when n=4).
                Short-desc drawn below the pill in every slot.
  Col 2 (55 %): grandchildren in a **zigzag** layout:
                  even-indexed col-1 parents  → FAR  sub-column (right side)
                  odd-indexed  col-1 parents  → NEAR sub-column (left side)
                Up to 4 gc per parent, filling their parent's vertical band.

Arrows: S-curve bezier that starts at the right edge of the source pill and
        lands at the left edge of the target pill (with a small arrowhead).

"""

import os
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import (
    Property, QEasingCurve, QObject, QPointF, QPropertyAnimation,
    QRectF, Qt, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics, QPainter,
    QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from config import SIDECAR_FILENAME
from core.sidecar import load_sidecar

# max children from grandparent and parent
MAX_C1 = 4   
MAX_C2 = 4   


# Data model

@dataclass
class TreeNode:
    name:         str
    path:         str
    is_folder:    bool
    short_desc:   str  = ""
    long_desc:    str  = ""
    sensitive:    bool = False
    manual:       bool = False
    children:     list = field(default_factory=list)
    child_offset: int  = 0


def _node_color(name: str, is_folder: bool, level: int) -> QColor:
    if level == 0:
        return QColor("#e8a84c")
    if is_folder:
        return QColor("#50a8d0")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    CODE = {"py","js","ts","jsx","tsx","cpp","c","h","hpp","go","rs","java",
            "cs","swift","kt","rb","sh","bash","zsh","ps1","lua","php"}
    DOCS = {"md","txt","pdf","docx","doc","rst","rtf"}
    DATA = {"json","csv","xlsx","xls","yaml","yml","xml","sql","toml","jsonl"}
    IMGS = {"png","jpg","jpeg","svg","gif","webp","bmp"}
    if ext in CODE: return QColor("#4ec994")
    if ext in DOCS: return QColor("#a07ed0")
    if ext in DATA: return QColor("#e8944c")
    if ext in IMGS: return QColor("#e84ca8")
    if name.startswith("."): return QColor("#e06060")
    return QColor("#6b7390")


def build_tree(folder_path: str, depth: int = 0, max_depth: int = 2) -> TreeNode:
    name    = os.path.basename(folder_path) or folder_path
    sidecar = load_sidecar(folder_path)
    fe      = sidecar.get("folder", {})
    root    = TreeNode(
        name=name, path=folder_path, is_folder=True,
        short_desc=fe.get("short_desc", ""),
        long_desc =fe.get("long_desc", ""),
        sensitive =fe.get("sensitive_detected", False),
        manual    =fe.get("manual_lock", False),
    )
    if depth >= max_depth:
        return root
    try:
        entries = sorted(os.listdir(folder_path))
    except PermissionError:
        return root
    for entry in entries:
        if entry.startswith(".") or entry == SIDECAR_FILENAME:
            continue
        full = os.path.join(folder_path, entry)
        if os.path.isdir(full):
            root.children.append(build_tree(full, depth + 1, max_depth))
        else:
            fe2 = sidecar.get("files", {}).get(entry, {})
            root.children.append(TreeNode(
                name=entry, path=full, is_folder=False,
                short_desc=fe2.get("short_desc", ""),
                long_desc =fe2.get("long_desc", ""),
                sensitive =fe2.get("sensitive_detected", False),
                manual    =fe2.get("manual_lock", False),
            ))
    return root


# Layout items 

@dataclass
class DrawnNode:
    tree_node: TreeNode
    x:         float   # pill centre x
    y:         float   # pill centre y
    w:         float   # pill width
    h:         float   # pill height (may differ by level)
    level:     int
    col:       int


@dataclass
class HitArea:
    kind:     str    # 'col1-prev|next'  'col2-prev-N|col2-next-N'
    x:        float
    y:        float
    w:        float
    h:        float
    ref_node: Optional[TreeNode] = None


# Slide property 

class _SlideHolder(QObject):
    def __init__(self):
        super().__init__()
        self._v = 0.0
    def _get(self): return self._v
    def _set(self, v): self._v = v
    offset = Property(float, _get, _set)


# Mind-map widget

class MindMapWidget(QWidget):
    """Horizontal mind-map graph view."""

    node_hovered  = Signal(str, str)
    node_selected = Signal(str)

    # ── layout constants
    PILL_H0   = 40    # root pill height
    PILL_H1   = 38    # col-1 pill height
    PILL_H2   = 26    # col-2 pill height (compact grandchildren)
    COL_PAD   = 14    # horizontal padding inside each column band
    BTN_H     = 20    # col-1 scroll button height
    BTN_M     = 4     # col-1 scroll button margin
    BTN_H_GC  = 12    # col-2 scroll button height (smaller)
    BTN_M_GC  = 3     # col-2 scroll button margin
    MIN_PILL_GAP = 6  # minimum guaranteed gap between adjacent col-2 pills
    DESC_FS   = 9     # font size for below-pill description
    DESC_GAP  = 2     # px gap between pill bottom and desc text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._root_data:   Optional[TreeNode] = None
        self._root_stack:  list[TreeNode]     = []
        self._drawn_nodes: list[DrawnNode]    = []
        # edges: (cx_src, cy_src, cx_tgt, cy_tgt, color, src_pw, tgt_pw)
        self._edges:       list[tuple]        = []
        self._hit_areas:   list[HitArea]      = []
        self._hov_node:    Optional[DrawnNode] = None
        self._hov_hit:     Optional[HitArea]   = None
        self._card_pt:     QPointF             = QPointF(0, 0)

        self._slide_holder = _SlideHolder()
        self._slide_anim   = QPropertyAnimation(self._slide_holder, b"offset")
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._slide_anim.setDuration(300)
        self._slide_anim.valueChanged.connect(lambda _: self._canvas.update())
        self._slide_anim.finished.connect(self._on_slide_done)
        self._pending_root: Optional[TreeNode] = None
        self._slide_dir:    int                = -1
        self._sliding_out:  bool               = False

        self._build_header()

    # Header 

    def _build_header(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background:#161722;border-bottom:1px solid #252636;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 0, 12, 0)
        bl.setSpacing(8)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setFixedHeight(24)
        self._back_btn.setStyleSheet(
            "QPushButton{background:#21222d;color:#9aa3bf;border:1px solid #2e2f42;"
            "border-radius:5px;padding:0 10px;font-size:11px;}"
            "QPushButton:hover{background:#2a2b3e;color:#cdd3e8;}"
        )
        self._back_btn.hide()
        self._back_btn.clicked.connect(self.go_back)
        bl.addWidget(self._back_btn)

        self._breadcrumb = QLabel("")
        self._breadcrumb.setStyleSheet("color:#4a5070;font-size:11px;background:transparent;")
        bl.addWidget(self._breadcrumb, 1)

        hint = QLabel("hover → preview  ·  ▲/▼ scroll  ·  click folder to explore")
        hint.setStyleSheet("color:#252840;font-size:10px;background:transparent;")
        bl.addWidget(hint)

        outer.addWidget(bar)
        self._canvas = _Canvas(self)
        outer.addWidget(self._canvas, 1)

    # Public API

    def load_folder(self, folder_path: str):
        self._root_stack.clear()
        self._root_data = build_tree(folder_path)
        self._slide_holder._v = 0.0
        self._rebuild()
        self._update_nav()
        self._canvas.update()

    def refresh(self):
        if self._root_data:
            fresh = build_tree(self._root_data.path)
            fresh.child_offset = self._root_data.child_offset
            self._root_data = fresh
            self._rebuild()
            self._canvas.update()

    # Navigation

    def go_back(self):
        if self._root_stack:
            self._slide_to(self._root_stack.pop(), direction=1)

    def _dive_into(self, node: TreeNode):
        self._root_stack.append(self._root_data)
        self._slide_to(node, direction=-1)

    def _slide_to(self, node: TreeNode, direction: int):
        if self._sliding_out:
            return
        self._sliding_out = True
        self._pending_root = node
        self._slide_dir    = direction
        w = self._canvas.width()
        self._slide_anim.stop()
        self._slide_anim.setStartValue(0.0)
        self._slide_anim.setEndValue(direction * -w)
        self._slide_anim.start()

    def _on_slide_done(self):
        if self._sliding_out:
            self._sliding_out  = False
            self._root_data    = self._pending_root
            self._pending_root = None
            self._rebuild()
            self._update_nav()
            w = self._canvas.width()
            self._slide_holder._v = self._slide_dir * w
            self._slide_anim.setStartValue(self._slide_holder._v)
            self._slide_anim.setEndValue(0.0)
            self._slide_anim.start()

    def _update_nav(self):
        if not self._root_data:
            return
        self._back_btn.setVisible(bool(self._root_stack))
        crumbs = [n.name for n in self._root_stack] + [self._root_data.name]
        self._breadcrumb.setText("  /  ".join(crumbs))

    # Geometry layout

    def _rebuild(self):
        if not self._root_data:
            return

        W  = self._canvas.width()
        H  = self._canvas.height()
        CP = self.COL_PAD
        BH = self.BTN_H
        BM = self.BTN_M

        w0 = W * 0.20
        w1 = W * 0.25
        c2_start = w0 + w1
        c2_width = W * 0.55

        near_cx = c2_start + c2_width * 0.27
        far_cx  = c2_start + c2_width * 0.76

        near_pw = max(60.0, c2_width * 0.48 - 2 * CP)
        far_pw  = max(60.0, c2_width * 0.48 - 2 * CP)

        cx0 = w0 * 0.5
        cx1 = w0 + w1 * 0.5
        pw0 = max(40.0, w0 - 2 * CP)
        pw1 = max(40.0, w1 - 2 * CP)

        nodes = []
        edges = []
        hits  = []

        r = self._root_data

        root_dn = DrawnNode(r, cx0, H / 2, pw0, self.PILL_H0, 0, 0)
        nodes.append(root_dn)

        all_c = r.children
        o1    = r.child_offset
        vis1  = all_c[o1:o1 + MAX_C1]
        n1    = len(vis1)

        has_c1_scroll = len(all_c) > MAX_C1
        if has_c1_scroll:
            c1_top = BM + BH + BM
            c1_bot = H - BM - BH - BM
            hits.append(HitArea("col1-prev", cx1, BM + BH / 2, pw1, BH, r))
            hits.append(HitArea("col1-next", cx1, H - BM - BH / 2, pw1, BH, r))
        else:
            c1_top = 0.0
            c1_bot = H
        c1_area = c1_bot - c1_top
        slot_h  = c1_area / max(n1, 1)

        child_dns = []
        for i, c in enumerate(vis1):
            cy1 = c1_top + slot_h * (i + 0.5)
            col = _node_color(c.name, c.is_folder, 1)
            dn1 = DrawnNode(c, cx1, cy1, pw1, self.PILL_H1, 1, 1)
            nodes.append(dn1)
            child_dns.append(dn1)
            edges.append((cx0, H / 2, cx1, cy1, col, pw0, pw1))

        BH_GC = self.BTN_H_GC
        BM_GC = self.BTN_M_GC

        for idx, (c, c_dn) in enumerate(zip(vis1, child_dns)):
            band_top = c1_top + slot_h * idx
            band_bot = c1_top + slot_h * (idx + 1)

            ac   = c.children
            o2   = c.child_offset
            vis2 = ac[o2:o2 + MAX_C2]
            n2   = len(vis2)
            if n2 == 0:
                continue

            # Even-indexed parents → FAR sub-col, odd → NEAR
            is_far = (idx % 2 == 0)
            cx2 = far_cx  if is_far else near_cx
            pw2 = far_pw  if is_far else near_pw

            has_gc_scroll = len(ac) > MAX_C2
            if has_gc_scroll:
                # Use smaller col-2 buttons so pills have more breathing room
                gc_area_top = band_top + BM_GC + BH_GC + BM_GC
                gc_area_bot = band_bot - BM_GC - BH_GC - BM_GC
                hits.append(HitArea(
                    f"col2-prev-{idx}",
                    cx2, band_top + BM_GC + BH_GC / 2, pw2, BH_GC, c,
                ))
                hits.append(HitArea(
                    f"col2-next-{idx}",
                    cx2, band_bot - BM_GC - BH_GC / 2, pw2, BH_GC, c,
                ))
            else:
                gc_area_top = band_top
                gc_area_bot = band_bot

            # Gap-based distribution: (n2+1) equal gaps fill leftover space.
            # gap = (available - total_pill_height) / (n2+1), clamped to MIN.
            gc_area  = gc_area_bot - gc_area_top
            PH2      = self.PILL_H2
            total_ph = n2 * PH2
            raw_gap  = (gc_area - total_ph) / (n2 + 1)
            gap      = max(self.MIN_PILL_GAP, raw_gap)
            for j, gc in enumerate(vis2):
                gy   = gc_area_top + gap * (j + 1) + PH2 * j + PH2 / 2
                gcol = _node_color(gc.name, gc.is_folder, 2)
                gc_dn = DrawnNode(gc, cx2, gy, pw2, PH2, 2, 2)
                nodes.append(gc_dn)
                edges.append((cx1, c_dn.y, cx2, gy, gcol, pw1, pw2))

        self._drawn_nodes = nodes
        self._edges       = edges
        self._hit_areas   = hits

    def paint(self, painter: QPainter):
        if not self._root_data:
            painter.setPen(QColor("#3a4060"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(
                self._canvas.rect(), Qt.AlignCenter,
                "Open a folder to view the mind map",
            )
            return

        W = self._canvas.width()
        H = self._canvas.height()
        dx = self._slide_holder._v
        painter.translate(dx, 0)

        # Column separator lines: col0/col1 and col1/col2
        sep_pen = QPen(QColor("#1e2030"), 1, Qt.DashLine)
        sep_pen.setDashPattern([2, 12])
        painter.setPen(sep_pen)
        for lx in [W * 0.20, W * 0.45]:
            painter.drawLine(QPointF(lx, 0), QPointF(lx, H))

        # Bezier connectors
        for (x1, y1, x2, y2, col, spw, tpw) in self._edges:
            c = QColor(col)
            c.setAlphaF(0.28)
            painter.setPen(QPen(c, 1.2))
            painter.setBrush(Qt.NoBrush)

            sx    = x1 + spw / 2   # right edge of source pill
            ex    = x2 - tpw / 2   # left  edge of target pill
            mid_x = (sx + ex) / 2

            path = QPainterPath()
            path.moveTo(sx, y1)
            path.cubicTo(mid_x, y1, mid_x, y2, ex, y2)
            painter.drawPath(path)

            # arrowhead at target end
            c.setAlphaF(0.60)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(c))
            ah   = 5.0
            arr  = QPainterPath()
            arr.moveTo(ex, y2)
            arr.lineTo(ex - ah, y2 - ah * 0.5)
            arr.lineTo(ex - ah, y2 + ah * 0.5)
            arr.closeSubpath()
            painter.drawPath(arr)

        # Nodes
        for dn in self._drawn_nodes:
            self._draw_node(painter, dn)

        # Scroll buttons
        for ha in self._hit_areas:
            self._draw_scroll_btn(painter, ha)

        # Hover card
        if self._hov_node:
            self._draw_card(painter, self._hov_node, W, H)

        painter.resetTransform()

    # Node drawing 

    def _draw_node(self, painter: QPainter, dn: DrawnNode):
        col  = _node_color(dn.tree_node.name, dn.tree_node.is_folder, dn.level)
        is_h = self._hov_node is dn
        is_r = dn.level == 0
        is_1 = dn.level == 1

        px = dn.x - dn.w / 2
        py = dn.y - dn.h / 2
        PW = dn.w
        PH = dn.h
        R  = PH / 2   # fully-rounded pill

        # glow
        if is_h or is_r:
            gc = QColor(col)
            gc.setAlphaF(0.12 if is_r else 0.07)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gc))
            painter.drawRoundedRect(QRectF(px - 4, py - 4, PW + 8, PH + 8), R + 3, R + 3)

        # pill fill
        bg = QColor(col)
        bg.setAlphaF(0.13 if is_r else (0.09 if is_h else 0.05))
        painter.setBrush(QBrush(bg))

        # pill border
        sc = QColor(col)
        sc.setAlphaF(1.0 if (is_h or is_r) else 0.40)
        lw = 1.8 if is_r else (1.4 if is_h else 0.9)
        painter.setPen(QPen(sc, lw))
        painter.drawRoundedRect(QRectF(px, py, PW, PH), R, R)

        # colour dot (left side)
        dot_r = 4.5 if is_r else 3.5
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(col))
        painter.drawEllipse(QPointF(px + R, dn.y), dot_r, dot_r)

        # Name text 
        fs   = 11 if is_r else (10 if is_1 else 9)
        bold = QFont.DemiBold if is_r else QFont.Normal
        font = QFont("Segoe UI", fs, bold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        text_x  = px + R * 2 + 6
        avail_w = PW - R * 2 - 10

        elided = fm.elidedText(dn.tree_node.name, Qt.ElideRight, int(avail_w))

        name_col = (
            QColor("#f0f0f8") if is_h else
            QColor("#e8a84c") if is_r else
            QColor("#cdd3e8")
        )
        painter.setPen(name_col)
        painter.drawText(QPointF(text_x, dn.y + fm.ascent() / 2 - 1), elided)

        # tag icons
        if dn.tree_node.sensitive:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#c05050"))
            painter.drawText(QPointF(px + PW - R - 16, dn.y + 4), "⚠")
        elif dn.tree_node.manual:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#4080a0"))
            painter.drawText(QPointF(px + PW - R - 16, dn.y + 4), "✏")

        # Short desc BELOW the pill (col-0 and col-1 only)
        # Col-2 grandchildren are too dense for desc-below; use hover card.
        if dn.level < 2 and dn.tree_node.short_desc:
            dfont = QFont("Segoe UI", self.DESC_FS)
            dfm   = QFontMetrics(dfont)
            desc_y = dn.y + PH / 2 + self.DESC_GAP + dfm.ascent()
            painter.setFont(dfont)
            painter.setPen(QColor("#6070a0") if is_h else QColor("#3a4460"))
            max_dw   = avail_w
            elided_d = dfm.elidedText(dn.tree_node.short_desc, Qt.ElideRight, int(max_dw))
            painter.drawText(QPointF(text_x - 2, desc_y), elided_d)

    # Scroll buttons

    def _draw_scroll_btn(self, painter: QPainter, ha: HitArea):
        is_prev = "prev" in ha.kind
        is_h    = self._hov_hit is ha
        label   = "▲" if is_prev else "▼"
        max_v   = MAX_C1 if "col1" in ha.kind else MAX_C2

        node     = ha.ref_node
        disabled = False
        if node:
            disabled = (
                (is_prev and node.child_offset == 0) or
                (not is_prev and node.child_offset + max_v >= len(node.children))
            )

        bg = QColor("#1c1d2a" if not is_h else "#21222d")
        painter.setPen(QPen(QColor("#2a2b3a"), 1))
        painter.setBrush(QBrush(bg))
        bx = ha.x - ha.w / 2
        by = ha.y - ha.h / 2
        painter.drawRoundedRect(QRectF(bx, by, ha.w, ha.h), 4, 4)

        font = QFont("Segoe UI", 9)
        fm   = QFontMetrics(font)
        tw   = fm.horizontalAdvance(label)
        painter.setFont(font)

        if disabled:
            painter.setPen(QColor("#252636"))
        elif is_h:
            painter.setPen(QColor("#e8a84c"))
        else:
            painter.setPen(QColor("#4a5070"))
        painter.drawText(QPointF(ha.x - tw / 2, ha.y + fm.ascent() / 2 - 1), label)

        # Pagination hint
        if node and len(node.children) > max_v:
            o   = node.child_offset
            tot = len(node.children)
            vis = min(max_v, tot - o)
            sf  = QFont("Segoe UI", 8)
            painter.setFont(sf)
            painter.setPen(QColor("#2e3450"))
            sfm = QFontMetrics(sf)
            cnt = f"{o + 1}–{o + vis}/{tot}"
            painter.drawText(
                QPointF(ha.x + ha.w / 2 + 5, ha.y + sfm.ascent() / 2 - 1), cnt
            )

    # Hover card

    def _draw_card(self, painter: QPainter, dn: DrawnNode, W: float, H: float):
        d  = dn.tree_node
        cw, ch = 275, 168

        mx = self._card_pt.x()
        my = self._card_pt.y()
        cx = mx + 20
        cy = my - ch - 12
        if cx + cw > W - 8:  cx = mx - cw - 20
        if cy < 8:            cy = my + 20
        if cx < 8:            cx = 8.0
        if cy + ch > H - 8:  cy = H - ch - 8

        bg = QColor("#0a0c14")
        bg.setAlphaF(0.97)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(QColor("#32344e"), 1.0))
        painter.drawRoundedRect(QRectF(cx, cy, cw, ch), 9, 9)

        col = _node_color(d.name, d.is_folder, dn.level)
        painter.setBrush(QBrush(col))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx + 14, cy + 18), 4.0, 4.0)

        painter.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        painter.setPen(QColor("#e8e8f0"))
        nm = d.name if len(d.name) <= 33 else d.name[:32] + "…"
        painter.drawText(QPointF(cx + 26, cy + 22), nm)

        type_lbl = "FOLDER" if d.is_folder else (
            d.name.rsplit(".", 1)[-1].upper() + " FILE" if "." in d.name else "FILE"
        )
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#3e4468"))
        painter.drawText(QPointF(cx + 26, cy + 34), type_lbl)

        painter.setPen(QPen(QColor("#1a1c2c"), 0.5))
        painter.drawLine(QPointF(cx + 10, cy + 42), QPointF(cx + cw - 10, cy + 42))

        desc = d.long_desc or d.short_desc or "No description yet."
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor("#cdd3e8"))
        painter.drawText(
            QRectF(cx + 12, cy + 50, cw - 24, 86),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            desc,
        )

        painter.setFont(QFont("Segoe UI", 8))
        if d.is_folder and dn.level < 2:
            painter.setPen(QColor("#2a2e50"))
            painter.drawText(QPointF(cx + 12, cy + ch - 9), "↵ click to explore")
        if d.sensitive:
            painter.setPen(QColor("#c05050"))
            painter.drawText(QPointF(cx + cw - 84, cy + ch - 9), "⚠ sensitive")
        elif d.manual:
            painter.setPen(QColor("#306880"))
            painter.drawText(QPointF(cx + cw - 66, cy + ch - 9), "✏ manual")

    # Mouse events

    def mouse_move(self, pos: QPointF):
        adj = QPointF(pos.x() - self._slide_holder._v, pos.y())
        mx, my = adj.x(), adj.y()
        self._card_pt = pos

        ha = self._find_hit(mx, my)
        dn = None if ha else self._find_node(mx, my)
        changed = (ha is not self._hov_hit) or (dn is not self._hov_node)
        self._hov_hit  = ha
        self._hov_node = dn
        if dn:
            self.node_hovered.emit(dn.tree_node.path, dn.tree_node.short_desc)
        clickable = ha is not None or (
            dn is not None and (
                (dn.tree_node.is_folder and dn.level > 0) or
                not dn.tree_node.is_folder
            )
        )
        self._canvas.setCursor(
            QCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)
        )
        if changed:
            self._canvas.update()

    def mouse_press(self, pos: QPointF):
        adj = QPointF(pos.x() - self._slide_holder._v, pos.y())
        mx, my = adj.x(), adj.y()
        ha = self._find_hit(mx, my)
        if ha:
            self._handle_hit(ha)
            return
        dn = self._find_node(mx, my)
        if dn and dn.tree_node.is_folder and dn.level > 0:
            self._dive_into(dn.tree_node)
        elif dn:
            self.node_selected.emit(dn.tree_node.path)

    def _handle_hit(self, ha: HitArea):
        node  = ha.ref_node
        if not node:
            return
        max_v = MAX_C1 if "col1" in ha.kind else MAX_C2
        if "prev" in ha.kind:
            node.child_offset = max(0, node.child_offset - max_v)
        elif "next" in ha.kind:
            node.child_offset = min(
                node.child_offset + max_v,
                max(0, len(node.children) - max_v),
            )
        self._rebuild()
        self._canvas.update()

    def mouse_leave(self):
        self._hov_node = None
        self._hov_hit  = None
        self._canvas.update()

    def canvas_resized(self):
        self._rebuild()
        self._canvas.update()

    # Hit testing

    def _find_node(self, mx: float, my: float) -> Optional[DrawnNode]:
        for dn in reversed(self._drawn_nodes):
            if abs(mx - dn.x) <= dn.w / 2 and abs(my - dn.y) <= dn.h / 2:
                return dn
        return None

    def _find_hit(self, mx: float, my: float) -> Optional[HitArea]:
        for ha in self._hit_areas:
            if abs(mx - ha.x) <= ha.w / 2 and abs(my - ha.y) <= ha.h / 2:
                return ha
        return None


# Canvas sub-widget 

class _Canvas(QWidget):
    def __init__(self, ctrl: MindMapWidget):
        super().__init__(ctrl)
        self._ctrl = ctrl
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d0e12"))
        self._ctrl.paint(p)
        p.end()

    def resizeEvent(self, _):
        self._ctrl.canvas_resized()

    def mouseMoveEvent(self, e):
        self._ctrl.mouse_move(QPointF(e.position()))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._ctrl.mouse_press(QPointF(e.position()))

    def leaveEvent(self, _):
        self._ctrl.mouse_leave()


# Backwards-compat alias
RadialTreeWidget = MindMapWidget