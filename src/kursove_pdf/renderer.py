"""Portable A4 renderer. No network, database or user-data files."""

from datetime import date
from functools import lru_cache
from importlib.resources import files
from io import BytesIO
from threading import RLock
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Flowable,
    Paragraph,
    Spacer,
)
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

W, H = A4
M = 34
CONTENT = W - 2 * M
DARK = HexColor("#111111")
GRAY = HexColor("#666666")
LINE = HexColor("#999999")

# ReportLab shares font state across documents; serialize render work in this process.
LOCK = RLock()


@lru_cache(maxsize=1)
def font_codepoints():
    for name, filename in [
        ("Body", "DejaVuSansCondensed.ttf"),
        ("Strong", "DejaVuSansCondensed-Bold.ttf"),
        ("Title", "DejaVuSans-Bold.ttf"),
    ]:
        pdfmetrics.registerFont(
            TTFont(name, str(files("kursove_pdf").joinpath("fonts", filename)))
        )
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Strong")
    return frozenset(pdfmetrics.getFont("Body").face.charToGlyph) & frozenset(
        pdfmetrics.getFont("Strong").face.charToGlyph
    )


def para(value, size=10.5, leading=13, bold=False, color=DARK, font=None):
    text = escape(str(value)).replace("\n", "<br/>").replace("\t", "    ")
    return Paragraph(
        text,
        ParagraphStyle(
            "p",
            fontName=font or ("Strong" if bold else "Body"),
            fontSize=size,
            leading=leading,
            textColor=color,
            splitLongWords=True,
        ),
    )


def optional(value):
    return str(value) if value and str(value).strip() else "не е посочен"


def draw_text(c, value, x, y, size=10.5, bold=False, color=DARK):
    c.setFont("Strong" if bold else "Body", size)
    c.setFillColor(color)
    c.drawString(x, y, str(value))


def draw_qr(c, payload, x, y, size):
    q = QrCodeWidget(payload, barLevel="M", barBorder=4)
    x0, y0, x1, y1 = q.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(q)
    renderPDF.draw(d, c, x, y)


class Header(Flowable):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.title = para(data["name"], 21, 25, True, font="Title")
        self.identifier = para("ID " + data["id"], 13, 16, True)
        self.creator = para(data["created_by"], 10.5, 13)

    def wrap(self, aW, aH):
        self.tw, self.th = self.title.wrap(383, H)
        _, self.ih = self.identifier.wrap(383, H)
        _, self.ch = self.creator.wrap(228, H)
        self.width = CONTENT
        self.height = max(118, self.th + self.ih + self.ch + 43)
        return self.width, self.height

    def draw(self):
        c = self.canv
        self.title.drawOn(c, 0, self.height - self.th)
        self.identifier.drawOn(c, 0, self.height - self.th - 8 - self.ih)
        draw_qr(c, self.data["id"], CONTENT - 128, self.height - 113, 128)
        baseline = max(39, self.ch + 19)
        draw_text(c, "ДАТА НА КУРСА", 0, baseline, 8, True, GRAY)
        draw_text(
            c,
            date.fromisoformat(self.data["date"]).strftime("%d.%m.%Y"),
            0,
            baseline - 17,
            12,
            True,
        )
        draw_text(c, "СЪЗДАЛ", 153, baseline, 8, True, GRAY)
        self.creator.drawOn(c, 153, baseline - 6 - self.ch)
        c.setStrokeColor(DARK)
        c.setLineWidth(0.9)
        c.line(0, 0, CONTENT, 0)


class Note(Flowable):
    def __init__(self, p, continued=False):
        super().__init__()
        self.p = p
        self.continued = continued

    def wrap(self, aW, aH):
        _, self.ph = self.p.wrap(CONTENT - 25, H)
        self.width = CONTENT
        self.height = self.ph + 28
        return self.width, self.height

    def split(self, aW, aH):
        if aH < 54:
            return []
        parts = self.p.split(CONTENT - 25, aH - 28)
        if len(parts) != 2:
            return []
        return [Note(parts[0], self.continued), Note(parts[1], True)]

    def draw(self):
        c = self.canv
        c.setFillColor(HexColor("#f3f3f3"))
        c.rect(0, 0, CONTENT, self.height, stroke=0, fill=1)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.rect(0, 0, CONTENT, self.height, stroke=1, fill=0)
        label = "БЕЛЕЖКА ЗА КУРСА" + (" (продължение)" if self.continued else "")
        draw_text(c, label, 11, self.height - 13, 8, True, GRAY)
        self.p.drawOn(c, 11, 8)


class ContactRow(Flowable):
    def __init__(self, name, phone):
        super().__init__()
        self.name = name
        self.phone = phone

    def wrap(self, aW, aH):
        self.width = aW
        self.left_width = min(266, aW * 0.64)
        self.right_width = aW - self.left_width - 12
        _, self.nh = self.name.wrap(self.left_width, H)
        _, self.ph = self.phone.wrap(self.right_width, H)
        self.height = max(self.nh, self.ph)
        return self.width, self.height

    def split(self, aW, aH):
        self.wrap(aW, aH)
        pieces = []
        for p, w, h in [
            (self.name, self.left_width, self.nh),
            (self.phone, self.right_width, self.ph),
        ]:
            parts = p.split(w, aH) if h > aH else [p, para("")]
            if len(parts) != 2:
                return []
            pieces.append(parts)
        return [ContactRow(pieces[0][i], pieces[1][i]) for i in (0, 1)]

    def draw(self):
        self.name.drawOn(self.canv, 0, self.height - self.nh)
        self.phone.drawOn(self.canv, self.left_width + 12, self.height - self.ph)


class OrderRow(Flowable):
    """A table row with splittable address/contact content and repeated document numbers."""

    def __init__(self, order, index, extra_phone=False, body=None, continued=False):
        super().__init__()
        self.order, self.index, self.extra_phone = order, index, extra_phone
        self.continued = continued
        self.docs = para(
            f"СН {order['warehouse_order']}  |  Фактура {order['invoice']}",
            8.5,
            12,
            color=GRAY,
        )
        self.body = (
            body
            if body is not None
            else [
                (para(order["address"], 10, 12, True), 3),
                (
                    ContactRow(
                        para("Получател: " + optional(order.get("recipient")), 9, 12),
                        para(optional(order.get("recipient_phone")), 9.5, 12, True),
                    ),
                    3,
                ),
            ]
        )
        if body is None and extra_phone:
            self.body.append(
                (
                    para(
                        "Тел. по фирмена регистрация: "
                        + optional(order.get("company_phone")),
                        8.5,
                        11,
                        color=GRAY,
                    ),
                    3,
                )
            )

    def wrap(self, aW, aH):
        self.inner = CONTENT - 105
        _, self.dh = self.docs.wrap(self.inner, H)
        self.header_h = 8 + self.dh + (11 if self.continued else 0)
        self.parts_h = [p.wrap(self.inner, H)[1] + gap for p, gap in self.body]
        self.width = CONTENT
        self.height = self.header_h + sum(self.parts_h) + 8
        return self.width, self.height

    def split(self, aW, aH):
        self.wrap(aW, aH)
        room = aH - self.header_h - 8
        if room < 26:
            return []
        left = []
        right = []
        for i, ((p, gap), ph) in enumerate(zip(self.body, self.parts_h)):
            if ph <= room:
                left.append((p, gap))
                room -= ph
            else:
                parts = p.split(self.inner, room - gap) if room - gap >= 12 else []
                if len(parts) == 2:
                    left.append((parts[0], gap))
                    right = [(parts[1], 0)] + self.body[i + 1 :]
                else:
                    right = self.body[i:]
                break
        if not left or not right:
            return []
        return [
            OrderRow(self.order, self.index, self.extra_phone, left, self.continued),
            OrderRow(self.order, self.index, self.extra_phone, right, True),
        ]

    def draw(self):
        c = self.canv
        top = self.height
        c.setFillColor(white if self.index % 2 else HexColor("#f3f3f3"))
        c.rect(0, 0, CONTENT, top, stroke=0, fill=1)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.rect(0, 0, CONTENT, top, stroke=1, fill=0)
        c.line(29, 0, 29, top)
        c.line(CONTENT - 60, 0, CONTENT - 60, top)
        draw_text(c, f"{self.index:02}", 7, top - 32, 10, True)
        self.docs.drawOn(c, 37, top - 8 - self.dh)
        y = top - self.header_h
        if self.continued:
            draw_text(c, "нареждане - продължение", 37, y + 1, 8, color=GRAY)
        for (p, gap), ph in zip(self.body, self.parts_h):
            y -= ph
            p.drawOn(c, 37, y)
        c.setFillColor(DARK)
        c.setFont("Strong", 15)
        c.drawCentredString(CONTENT - 30, top - 28, str(self.order["product_count"]))
        c.setFont("Body", 7)
        c.drawCentredString(
            CONTENT - 30,
            top - 41,
            "ПОЗИЦИЯ" if self.order["product_count"] == 1 else "ПОЗИЦИИ",
        )


class ClientBlock(Flowable):
    """Repeat the customer heading on each fragment; exactly one handwritten checkbox per run."""

    def __init__(self, group, rows, fresh_height, continued=False, section=None):
        super().__init__()
        self.group, self.rows, self.fresh_height, self.continued = (
            group,
            rows,
            fresh_height,
            continued,
        )
        self.section = section
        self.client = para(group.client, 11.5, 14, True, color=white)
        label = (
            "Тел. по фирмена регистрация: " + group.common_phone
            if group.common_phone is not None
            else "Фирмени телефони: посочени към нарежданията"
        )
        self.phone = para(label, 8.5, 11, color=HexColor("#dddddd"))

    def wrap(self, aW, aH):
        _, self.ch = self.client.wrap(CONTENT - 128, H)
        _, self.ph = self.phone.wrap(CONTENT - 128, H)
        self.group_h = max(43, 8 + self.ch + 3 + self.ph + 6)
        self.section_h = 24 if self.section else 0
        self.header_h = self.group_h + self.section_h
        self.row_heights = [r.wrap(aW, aH)[1] for r in self.rows]
        self.width = CONTENT
        self.height = self.header_h + sum(self.row_heights)
        return self.width, self.height

    def split(self, aW, aH):
        self.wrap(aW, aH)
        room = aH - self.header_h
        left = []
        right = []
        for i, (row, rh) in enumerate(zip(self.rows, self.row_heights)):
            if rh <= room:
                left.append(row)
                room -= rh
            else:
                # Preserve a normal row whole; only split one too tall for a fresh page.
                parts = (
                    row.split(aW, room) if rh > self.fresh_height - self.group_h else []
                )
                if len(parts) == 2:
                    left.append(parts[0])
                    right = [parts[1]] + self.rows[i + 1 :]
                else:
                    right = self.rows[i:]
                break
        if not left or not right:
            return []
        return [
            ClientBlock(
                self.group, left, self.fresh_height, self.continued, self.section
            ),
            ClientBlock(self.group, right, self.fresh_height, True),
        ]

    def draw(self):
        c = self.canv
        top = self.height - self.section_h
        if self.section:
            self.section.wrap(CONTENT, 24)
            self.section.drawOn(c, 0, top)
        gh = self.group_h
        split_x = CONTENT - 108
        c.setFillColor(DARK)
        c.rect(0, top - gh, split_x, gh, stroke=0, fill=1)
        self.client.drawOn(c, 10, top - 8 - self.ch)
        self.phone.drawOn(c, 10, top - 8 - self.ch - 3 - self.ph)
        c.setFillColor(white)
        c.rect(split_x, top - gh, 108, gh, stroke=0, fill=1)
        c.setStrokeColor(DARK)
        c.setLineWidth(0.7)
        c.rect(split_x, top - gh, 108, gh, stroke=1, fill=0)
        if not self.continued:
            qy = top - gh + (gh - 23) / 2
            c.setLineWidth(1)
            c.rect(split_x + 10, qy, 23, 23, stroke=1, fill=0)
            draw_text(c, "Доставен", split_x + 41, qy + 8, 9.5, True)
        else:
            draw_text(c, "продължение", split_x + 13, top - gh / 2 - 3, 9, color=GRAY)
        y = top - gh
        for row, rh in zip(self.rows, self.row_heights):
            y -= rh
            row.drawOn(c, 0, y)


class SectionHeading(Flowable):
    keepWithNext = True

    def __init__(self, group_count, order_count):
        super().__init__()
        self.group_count = group_count
        self.order_count = order_count

    def wrap(self, aW, aH):
        return CONTENT, 24

    def draw(self):
        draw_text(self.canv, "СКЛАДОВИ НАРЕЖДАНИЯ", 0, 12, 10, True)
        clients = "клиентска група" if self.group_count == 1 else "клиентски групи"
        orders = "нареждане" if self.order_count == 1 else "нареждания"
        self.canv.setFillColor(GRAY)
        self.canv.setFont("Body", 9)
        self.canv.drawRightString(
            CONTENT, 12, f"{self.group_count} {clients} / {self.order_count} {orders}"
        )


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, course_id="", sample=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.states = []
        self.course_id = course_id
        self.sample = sample

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setStrokeColor(HexColor("#bbbbbb"))
            self.setLineWidth(0.4)
            self.line(M, 29, W - M, 29)
            self.setFillColor(GRAY)
            self.setFont("Body", 7.5)
            if self.sample:
                self.drawString(M, 18, "ОБРАЗЕЦ - примерни данни")
            # Long IDs are wrapped in the repeated header; footer only holds page count.
            self.drawRightString(W - M, 18, f"стр. {self._pageNumber} / {total}")
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def generate_pdf(payload, *, sample=False):
    """Validate a v1 payload and return PDF bytes. Raises InputError on invalid input."""
    from .validation import validate

    with LOCK:
        font_codepoints()
        data = validate(payload)
        output = BytesIO()
        doc = BaseDocTemplate(
            output,
            pagesize=A4,
            title=f"Курс {data['id']} - {data['name']}",
            author="GStroy",
            allowSplitting=1,
        )

        def decorate(c, doc):
            c.saveState()
            if doc.page > 1:
                name = para(data["name"], 12, 15, True)
                _, nh = name.wrap(CONTENT - 96, 60)
                name.drawOn(c, M, H - 49 - nh)
                ident = para("ID " + data["id"], 10, 12)
                _, ih = ident.wrap(CONTENT - 96, 60)
                ident.drawOn(c, M, H - 54 - nh - ih)
                draw_qr(c, data["id"], W - M - 65, H - 105, 65)
            c.restoreState()

        first = Frame(
            M,
            43,
            CONTENT,
            755,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        # Determine room below the complete repeated title/ID, even for long identifiers.
        name = para(data["name"], 12, 15, True)
        _, nh = name.wrap(CONTENT - 96, H)
        ident = para("ID " + data["id"], 10, 12)
        _, ih = ident.wrap(CONTENT - 96, H)
        later_top = min(741, H - 54 - nh - ih - 16)
        later = Frame(
            M,
            43,
            CONTENT,
            later_top - 43,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        # Pass actual fresh-frame height into Order splitting via the rendering scope.
        doc.addPageTemplates(
            [
                PageTemplate(
                    "first", [first], onPage=decorate, autoNextPageTemplate="later"
                ),
                PageTemplate("later", [later], onPage=decorate),
            ]
        )
        from .grouping import group_orders

        groups = group_orders(data["orders"])
        story = [Header(data), Spacer(1, 11)]
        note = data.get("note")
        if note and note.strip():
            story.append(Note(para(note, 9.5, 12)))
        story.append(Spacer(1, 11))
        for group_index, group in enumerate(groups):
            rows = [
                OrderRow(order, index, extra_phone=group.common_phone is None)
                for index, order in group.orders
            ]
            section = (
                SectionHeading(len(groups), len(data["orders"]))
                if group_index == 0
                else None
            )
            story.extend(
                [
                    ClientBlock(group, rows, later_top - 43, section=section),
                    Spacer(1, 12),
                ]
            )
        doc.build(
            story,
            canvasmaker=lambda *a, **kw: NumberedCanvas(
                *a, course_id=data["id"], sample=sample, **kw
            ),
        )
        return output.getvalue()
