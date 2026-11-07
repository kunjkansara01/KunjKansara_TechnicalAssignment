"""Record a captioned, approximately six-minute live application demonstration.
Requires playwright, imageio-ffmpeg, Microsoft Edge and a running seeded app.
Run once with fresh sample CSV codes. The demo intentionally creates sample records.
"""

import time
from pathlib import Path
import subprocess
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
ENV = dotenv_values(ROOT / ".env")
OUTPUT = ROOT / "demo"
OUTPUT.mkdir(exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True, slow_mo=350)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1100},
        record_video_dir=str(OUTPUT),
        record_video_size={"width": 1440, "height": 1100},
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto("http://127.0.0.1:5000")
    started = time.monotonic()

    def chapter(number, title, description):
        page.evaluate(
            """([number, title, description]) => {
            let caption = document.getElementById('demo-caption');
            if (!caption) { caption = document.createElement('div'); caption.id='demo-caption'; document.body.append(caption); }
            Object.assign(caption.style, {position:'fixed', bottom:'0',left:'230px',right:'0',background:'#102e3a',color:'white',padding:'18px 26px',zIndex:'99999',fontFamily:'system-ui',pointerEvents:'none',borderTop:'4px solid #62d0b9'});
            caption.replaceChildren();
            const heading=document.createElement('strong'); heading.textContent=String(number).padStart(2,'0')+' / 13  '+title; heading.style.fontSize='18px';
            const detail=document.createElement('div'); detail.textContent=description; detail.style.marginTop='5px';detail.style.fontSize='15px';detail.style.color='#c9e0e7';
            caption.append(heading,detail);
        }""",
            [number, title, description],
        )
        print(f"Chapter {number}: {title}", flush=True)

    def hold(number):
        remaining = number * 26 - (time.monotonic() - started)
        if remaining > 0:
            page.wait_for_timeout(remaining * 1000)

    def nav(name):
        page.locator("#nav").get_by_role("button", name=name, exact=True).click()

    def create_order(quantity=2, second=True):
        nav("Orders")
        page.get_by_role("button", name="Create order", exact=True).click()
        page.locator("#customer").select_option("1")
        page.get_by_label("Product", exact=True).select_option("1")
        page.get_by_label("Quantity", exact=True).fill(str(quantity))
        if second:
            page.get_by_role("button", name="Add product", exact=True).click()
            page.get_by_label("Product", exact=True).nth(1).select_option("2")
            page.get_by_label("Quantity", exact=True).nth(1).fill("3")
        page.get_by_label("Discount %", exact=True).fill("10")
        page.get_by_role("button", name="Save draft", exact=True).click()
        page.get_by_role("button", name="Confirm saved order", exact=True).wait_for()

    chapter(
        1,
        "Sales order and inventory management",
        "Flask + JavaScript + MySQL. Secure login, customer records, orders, stock and reports in one local application.",
    )
    page.get_by_label("Email", exact=True).fill("admin@example.test")
    page.get_by_label("Password", exact=True).fill(ENV["SEED_ADMIN_PASSWORD"])
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.get_by_role("button", name="Create order", exact=True).wait_for()
    hold(1)

    chapter(
        2,
        "Customer master data",
        "Administrators maintain customer details. Search and status filters help find records. Referenced records are protected from deletion.",
    )
    nav("Customers")
    page.get_by_role("button", name="Add new", exact=True).click()
    page.get_by_label("Name", exact=True).fill("Demo Trading Company")
    page.get_by_label("Email", exact=True).fill("demo-buyer@example.test")
    page.get_by_label("Mobile", exact=True).fill("9876543210")
    page.get_by_label("City", exact=True).fill("Pune")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_label("Search", exact=True).fill("Demo Trading")
    page.get_by_role("button", name="Filter", exact=True).click()
    hold(2)

    chapter(
        3,
        "Products and opening stock",
        "Each product has a unique code, saved price, available quantity and activity status. All stock changes have an audit trail.",
    )
    nav("Products")
    page.get_by_role("button", name="Adjust stock", exact=True).first.wait_for()
    hold(3)

    chapter(
        4,
        "Create a multiple-item draft",
        "Two keyboards and three mice give a subtotal of INR 4,500. A 10% discount produces a total of INR 4,050.",
    )
    create_order()
    assert "4,050.00" in page.locator("#totals").inner_text()
    hold(4)

    chapter(
        5,
        "Confirm the order",
        "Confirmation checks every product and atomically saves stock deductions, movement records and status. Repeated requests cannot deduct again.",
    )
    page.get_by_role("button", name="Confirm saved order", exact=True).click()
    page.get_by_text("Order confirmed.", exact=True).wait_for()
    nav("Products")
    page.get_by_role("button", name="Adjust stock", exact=True).first.wait_for()
    hold(5)

    chapter(
        6,
        "Cancel and restore stock",
        "Cancelling a confirmed order restores its stock exactly once. The order becomes read-only and is excluded from sales reports.",
    )
    nav("Orders")
    page.get_by_role("button", name="Open", exact=True).first.click()
    page.get_by_role("button", name="Cancel order", exact=True).click()
    page.get_by_text("Order cancelled.", exact=True).wait_for()
    hold(6)

    chapter(
        7,
        "Reject insufficient stock",
        "This draft requests 999 keyboards. Confirmation fails and the transaction leaves the order and all stock unchanged.",
    )
    create_order(999, False)
    page.get_by_role("button", name="Confirm saved order", exact=True).click()
    page.get_by_text(
        "Insufficient stock or stock limit exceeded", exact=False
    ).wait_for()
    hold(7)

    chapter(
        8,
        "Reasoned stock adjustments",
        "Administrators can adjust stock with a mandatory reason. Negative resulting stock is rejected and every accepted change is recorded.",
    )
    nav("Products")
    page.get_by_role("button", name="Adjust stock", exact=True).first.click()
    page.get_by_label("Quantity change (use minus to decrease)", exact=True).fill("5")
    page.get_by_label("Reason", exact=True).fill("Physical count correction for demo")
    page.get_by_role("button", name="Save", exact=True).click()
    hold(8)

    chapter(
        9,
        "Validate the entire CSV before importing",
        "One invalid price rejects both rows. The response identifies the row and reason, and nothing is partially imported.",
    )
    nav("Import")
    page.get_by_label("CSV file", exact=True).set_input_files(
        str(ROOT / "samples/products_invalid.csv")
    )
    page.get_by_role("button", name="Validate and import", exact=True).click()
    page.get_by_text("Import rejected.", exact=False).wait_for()
    hold(9)

    chapter(
        10,
        "Import products with opening movements",
        "The valid file creates two products and records their opening quantities in the stock ledger within the same transaction.",
    )
    page.get_by_label("CSV file", exact=True).set_input_files(
        str(ROOT / "samples/products_valid.csv")
    )
    page.get_by_role("button", name="Validate and import", exact=True).click()
    page.get_by_text("2 products imported", exact=False).wait_for()
    nav("Products")
    hold(10)

    chapter(
        11,
        "Sales and low-stock reports",
        "Customer totals use confirmed orders after discount. Product totals use gross item values. Customers with no confirmed sales remain visible.",
    )
    create_order()
    page.get_by_role("button", name="Confirm saved order", exact=True).click()
    page.get_by_text("Order confirmed.", exact=True).wait_for()
    nav("Reports")
    page.locator("#report-form select").select_option("customers")
    page.get_by_role("button", name="Run report", exact=True).click()
    hold(11)

    chapter(
        12,
        "Audit history and product reporting",
        "The movement history connects each opening balance, adjustment, sale and cancellation to its product, user, reason and time.",
    )
    page.locator("#report-form select").select_option("products")
    page.get_by_role("button", name="Run report", exact=True).click()
    page.wait_for_timeout(4000)
    page.locator("#report-form select").select_option("low-stock")
    page.get_by_role("button", name="Run report", exact=True).click()
    page.wait_for_timeout(4000)
    page.locator("#report-form select").select_option("movements")
    page.get_by_role("button", name="Run report", exact=True).click()
    hold(12)

    chapter(
        13,
        "Sales user access and verification",
        "Sales users see active master data and their own orders. The submission includes MySQL tests, SQL, setup instructions, Git history and AI disclosure.",
    )
    page.get_by_role("button", name="Log out", exact=True).click()
    page.get_by_label("Email", exact=True).fill("sales@example.test")
    page.get_by_label("Password", exact=True).fill(ENV["SEED_SALES_PASSWORD"])
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.get_by_role("button", name="Create order", exact=True).wait_for()
    assert (
        page.locator("#nav").get_by_role("button", name="Reports", exact=True).count()
        == 0
    )
    hold(13)
    assert not errors, errors
    video = page.video
    context.close()
    path = video.path()
    browser.close()

output = OUTPUT / "Assignment_Demo.mp4"
subprocess.run(
    [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ],
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
print(f"Saved captioned demo: {output}", flush=True)
