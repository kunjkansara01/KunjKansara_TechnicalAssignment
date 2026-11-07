let user,
  token,
  currentPage = "orders",
  products = [],
  customers = [];
const content = document.querySelector("#content");
const dialog = document.querySelector("#dialog");
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const money = (value) =>
  Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
function message(text, error = false) {
  const element = document.querySelector("#message");
  element.textContent = text;
  element.className = error ? "error" : "";
}
async function api(path, method = "GET", data) {
  const headers = { "X-CSRF-Token": token || "" };
  let body;
  if (data instanceof FormData) body = data;
  else if (data !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(data);
  }
  const response = await fetch("/api/" + path, { method, headers, body });
  const result = response.status === 204 ? {} : await response.json();
  if (!response.ok) {
    const details = result.details
      ?.map((row) => `Row ${row.row}: ${row.reason}`)
      .join("\n");
    throw new Error([result.error, details].filter(Boolean).join("\n"));
  }
  return result;
}
async function busy(button, task) {
  button.disabled = true;
  try {
    await task();
  } catch (error) {
    message(error.message, true);
  } finally {
    button.disabled = false;
  }
}
function field(name, label, value = "", type = "text", extra = "") {
  return `<label>${label}<input name="${name}" type="${type}" value="${escapeHtml(value)}" required ${extra}></label>`;
}
function table(rows, columns, actions) {
  if (!rows.length) return '<p class="empty">No records to show.</p>';
  return `<div class="scroll"><table><thead><tr>${columns.map(([key, label]) => `<th>${label}</th>`).join("")}${actions ? "<th>Actions</th>" : ""}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([key]) => `<td>${key === "status" ? `<span class="badge ${escapeHtml(row[key])}">${escapeHtml(row[key])}</span>` : escapeHtml(row[key])}</td>`).join("")}${actions ? `<td>${actions(row)}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
}
function openEditor(title, html, save) {
  document.querySelector("#dialog-title").textContent = title;
  document.querySelector("#fields").innerHTML = html;
  document.querySelector("#form-error").textContent = "";
  document.querySelector("#editor").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      await save(Object.fromEntries(new FormData(event.target)));
      dialog.close();
      await navigate(currentPage);
    } catch (error) {
      document.querySelector("#form-error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  dialog.showModal();
}
document.querySelector("#close-dialog").onclick = () => dialog.close();
async function initialize() {
  const session = await api("session");
  user = session.user;
  token = session.csrf_token;
  if (!user) {
    document.querySelector("#nav").innerHTML = "";
    document.querySelector("#account").innerHTML = "";
    document.querySelector("#title").textContent = "Welcome back";
    content.innerHTML = `<form id="login" class="panel login"><h2>Sign in to Ledger</h2><p class="muted">Manage your orders, customers and stock.</p>${field("email", "Email", "", "email")}${field("password", "Password", "", "password")}<button>Sign in</button></form>`;
    document.querySelector("#login").onsubmit = (event) => {
      event.preventDefault();
      busy(event.submitter, async () => {
        await api(
          "login",
          "POST",
          Object.fromEntries(new FormData(event.target)),
        );
        message("");
        await initialize();
      });
    };
    return;
  }
  const pages = [
    "orders",
    "customers",
    "products",
    ...(user.role === "Admin" ? ["reports", "import"] : []),
  ];
  document.querySelector("#nav").innerHTML = pages
    .map(
      (page) =>
        `<button data-page="${page}">${page[0].toUpperCase() + page.slice(1)}</button>`,
    )
    .join("");
  document.querySelector("#nav").onclick = (event) => {
    if (event.target.dataset.page)
      navigate(event.target.dataset.page).catch((error) =>
        message(error.message, true),
      );
  };
  document.querySelector("#account").innerHTML =
    `<p>${escapeHtml(user.name)} · ${user.role}</p><button id="logout" class="secondary">Log out</button>`;
  document.querySelector("#logout").onclick = (event) =>
    busy(event.target, async () => {
      await api("logout", "POST");
      await initialize();
    });
  await navigate("orders");
}
async function allActive(kind) {
  const rows = [];
  let page = 1,
    result;
  do {
    result = await api(`${kind}?status=Active&page_size=100&page=${page++}`);
    rows.push(...result.items);
  } while (rows.length < result.total);
  return rows;
}
async function navigate(page) {
  currentPage = page;
  document.querySelector("#title").textContent = {
    orders: "Sales orders",
    customers: "Customers",
    products: "Products & stock",
    reports: "Business reports",
    import: "Import products",
  }[page];
  document
    .querySelectorAll("[data-page]")
    .forEach((button) =>
      button.classList.toggle("active", button.dataset.page === page),
    );
  if (page === "orders") await showOrders();
  else if (["customers", "products"].includes(page)) await showMaster(page);
  else if (page === "reports") await showReports();
  else showImport();
}
async function showMaster(kind, page = 1, query = "") {
  const result = await api(`${kind}?page=${page}&${query}`);
  const isProduct = kind === "products";
  const columns = isProduct
    ? [
        ["product_code", "Code"],
        ["name", "Product"],
        ["category", "Category"],
        ["price", "Price · INR"],
        ["stock_quantity", "Stock"],
        ["status", "Status"],
      ]
    : [
        ["name", "Customer"],
        ["email", "Email"],
        ["mobile", "Mobile"],
        ["city", "City"],
        ["status", "Status"],
      ];
  content.innerHTML = `<div class="panel"><form id="filters" class="toolbar"><input name="search" aria-label="Search" placeholder="Search ${kind}"><select name="status" aria-label="Status"><option value="">All statuses</option><option>Active</option><option>Inactive</option></select>${isProduct ? '<input name="category" aria-label="Category" placeholder="Category">' : ""}<button>Filter</button>${user.role === "Admin" ? '<button type="button" id="new">Add new</button>' : ""}</form>${table(result.items, columns, user.role === "Admin" ? (row) => `<button class="small secondary" data-edit="${row.id}">Edit</button>${isProduct ? `<button class="small secondary" data-stock="${row.id}">Adjust stock</button>` : ""}<button class="small danger" data-delete="${row.id}">Delete</button>` : null)}<footer><span>${result.total} records · Page ${page}</span><button id="previous" class="secondary" ${page === 1 ? "disabled" : ""}>Previous</button><button id="next" class="secondary" ${page * result.page_size >= result.total ? "disabled" : ""}>Next</button></footer></div>`;
  const params = new URLSearchParams(query);
  for (const [key, value] of params)
    if (document.querySelector("#filters").elements[key])
      document.querySelector("#filters").elements[key].value = value;
  document.querySelector("#filters").onsubmit = (event) => {
    event.preventDefault();
    busy(event.submitter, () =>
      showMaster(
        kind,
        1,
        new URLSearchParams(new FormData(event.target)).toString(),
      ),
    );
  };
  document.querySelector("#previous").onclick = (event) =>
    busy(event.target, () => showMaster(kind, page - 1, query));
  document.querySelector("#next").onclick = (event) =>
    busy(event.target, () => showMaster(kind, page + 1, query));
  function edit(row = {}) {
    let html = field("name", "Name", row.name);
    if (isProduct)
      html +=
        field("product_code", "Product code", row.product_code) +
        field("category", "Category", row.category) +
        field(
          "price",
          "Price · INR",
          row.price,
          "number",
          'min="0" step=".01"',
        ) +
        (!row.id
          ? field(
              "stock_quantity",
              "Opening stock",
              0,
              "number",
              'min="0" step="1"',
            )
          : "");
    else
      html +=
        field("email", "Email", row.email, "email") +
        field("mobile", "Mobile", row.mobile) +
        field("city", "City", row.city);
    html += `<label>Status<select name="status"><option ${row.status === "Active" ? "selected" : ""}>Active</option><option ${row.status === "Inactive" ? "selected" : ""}>Inactive</option></select></label>`;
    openEditor(row.id ? "Edit record" : "Add record", html, (data) =>
      api(kind + (row.id ? "/" + row.id : ""), row.id ? "PUT" : "POST", data),
    );
  }
  if (document.querySelector("#new"))
    document.querySelector("#new").onclick = () => edit();
  content.onclick = (event) => {
    const button = event.target;
    if (button.dataset.edit)
      edit(result.items.find((row) => row.id === Number(button.dataset.edit)));
    if (button.dataset.stock)
      openEditor(
        "Adjust stock",
        field(
          "quantity_change",
          "Quantity change (use minus to decrease)",
          "",
          "number",
          'step="1"',
        ) + field("reason", "Reason"),
        (data) => api(`products/${button.dataset.stock}/adjust`, "POST", data),
      );
    if (
      button.dataset.delete &&
      confirm("Delete this record? Referenced records must be deactivated.")
    )
      busy(button, async () => {
        await api(`${kind}/${button.dataset.delete}`, "DELETE");
        await showMaster(kind, page, query);
      });
  };
}
async function showOrders() {
  const result = await api("orders");
  const confirmed = result.items.filter(
    (order) => order.status === "Confirmed",
  );
  content.onclick = null;
  content.innerHTML = `<div class="grid"><div class="panel">Total orders<span class="metric">${result.items.length}</span></div><div class="panel">Draft orders<span class="metric">${result.items.filter((order) => order.status === "Draft").length}</span></div><div class="panel">Confirmed sales · INR<span class="metric">${money(confirmed.reduce((sum, order) => sum + Number(order.grand_total), 0))}</span></div></div><div class="panel"><div class="toolbar"><button id="new-order">Create order</button><span class="muted">Stock is deducted when you confirm an order.</span></div>${table(
    result.items,
    [
      ["order_number", "Order"],
      ["order_date", "Date"],
      ["customer_id", "Customer ID"],
      ["status", "Status"],
      ["grand_total", "Total · INR"],
    ],
    (row) =>
      `<button class="small secondary" data-order="${row.id}">Open</button>`,
  )}</div>`;
  document.querySelector("#new-order").onclick = (event) =>
    busy(event.target, () => orderEditor());
  content
    .querySelectorAll("[data-order]")
    .forEach(
      (button) =>
        (button.onclick = () =>
          busy(button, async () =>
            orderEditor(await api("orders/" + button.dataset.order)),
          )),
    );
}
async function orderEditor(order) {
  [products, customers] = await Promise.all([
    allActive("products"),
    allActive("customers"),
  ]);
  const editable = !order || order.status === "Draft";
  content.innerHTML = `<div class="panel"><div class="toolbar"><button id="back" class="secondary">Back to orders</button><span class="badge ${order?.status || "Draft"}">${order?.status || "New draft"}</span></div><h2>${escapeHtml(order?.order_number || "Create a sales order")}</h2><form id="order-form"><div class="grid"><label>Customer<select id="customer" aria-label="Customer" required ${!editable ? "disabled" : ""}><option value="">Select customer</option>${customers.map((customer) => `<option value="${customer.id}">${escapeHtml(customer.name)}</option>`).join("")}${order && !customers.some((c) => c.id === order.customer_id) ? `<option value="${order.customer_id}">Customer #${order.customer_id} (inactive)</option>` : ""}</select></label>${field("order_date", "Order date", order?.order_date || new Date().toLocaleDateString("en-CA"), "date")}${field("discount", "Discount %", order?.discount_percentage || 0, "number", 'min="0" max="20" step=".01"')}</div><p class="muted">Product · available stock / quantity / saved rate / amount. Currency INR.</p><div id="items"></div>${editable ? '<button type="button" id="add-row" class="secondary">Add product</button>' : ""}<div id="totals" class="totals"></div><footer>${editable ? '<button type="submit">Save draft</button>' : ""}${order && order.status === "Draft" ? '<button type="button" id="confirm">Confirm saved order</button>' : ""}${order && order.status !== "Cancelled" ? '<button type="button" id="cancel" class="danger">Cancel order</button>' : ""}</footer></form></div>`;
  document.querySelector("#back").onclick = () => navigate("orders");
  document.querySelector("#customer").value = order?.customer_id || "";
  const form = document.querySelector("#order-form");
  if (!editable)
    form.querySelectorAll("input").forEach((input) => (input.disabled = true));
  function recalculate() {
    let subtotal = 0;
    document.querySelectorAll(".order-row").forEach((row) => {
      const amount =
        Number(row.dataset.rate || 0) *
        Number(row.querySelector("input").value);
      row.querySelector(".amount").textContent = money(amount);
      subtotal += amount;
    });
    const discount = (subtotal * Number(form.elements.discount.value)) / 100;
    document.querySelector("#totals").innerHTML =
      `<p><span>Subtotal</span><strong>${money(subtotal)}</strong></p><p><span>Discount</span><strong>${money(discount)}</strong></p><p><span>Grand total · INR</span><strong>${money(subtotal - discount)}</strong></p><small>Final values are calculated by the server.</small>`;
  }
  function addRow(item) {
    const row = document.createElement("div");
    row.className = "order-row";
    row.dataset.rate = item?.rate || 0;
    row.innerHTML = `<select aria-label="Product" required ${!editable ? "disabled" : ""}><option value="">Select product</option>${products.map((product) => `<option value="${product.id}">${escapeHtml(product.name)} · ${product.stock_quantity} available</option>`).join("")}${item && !products.some((p) => p.id === item.product_id) ? `<option value="${item.product_id}">Product #${item.product_id} (inactive)</option>` : ""}</select><input aria-label="Quantity" type="number" min="1" step="1" required value="${item?.quantity || 1}" ${!editable ? "disabled" : ""}><span class="rate">${money(item?.rate || 0)}</span><strong class="amount"></strong>${editable ? '<button type="button" class="danger small">Remove</button>' : ""}`;
    row.querySelector("select").value = item?.product_id || "";
    row.querySelector("select").onchange = () => {
      const selected = products.find(
        (product) => product.id === Number(row.querySelector("select").value),
      );
      const saved = order?.items.find((i) => i.product_id === selected?.id);
      row.dataset.rate = saved?.rate || selected?.price || 0;
      row.querySelector(".rate").textContent = money(row.dataset.rate);
      recalculate();
    };
    row.querySelector("input").oninput = recalculate;
    if (editable)
      row.querySelector("button").onclick = () => {
        row.remove();
        recalculate();
      };
    document.querySelector("#items").append(row);
    recalculate();
  }
  (order?.items || [null]).forEach(addRow);
  if (editable) document.querySelector("#add-row").onclick = () => addRow();
  form.elements.discount.oninput = recalculate;
  form.onsubmit = (event) => {
    event.preventDefault();
    busy(event.submitter, async () => {
      const items = [...document.querySelectorAll(".order-row")].map((row) => ({
        product_id: Number(row.querySelector("select").value),
        quantity: row.querySelector("input").value,
      }));
      if (!items.length) throw new Error("Add at least one product.");
      if (new Set(items.map((item) => item.product_id)).size !== items.length)
        throw new Error("Remove duplicate products.");
      const saved = await api(
        "orders" + (order ? "/" + order.id : ""),
        order ? "PUT" : "POST",
        {
          customer_id: Number(document.querySelector("#customer").value),
          order_date: form.elements.order_date.value,
          discount_percentage: form.elements.discount.value,
          items,
        },
      );
      message("Draft saved.");
      await orderEditor(saved);
    });
  };
  for (const action of ["confirm", "cancel"]) {
    const button = document.querySelector("#" + action);
    if (button)
      button.onclick = () => {
        if (
          confirm(
            `${action === "confirm" ? "Confirm the saved order and deduct stock? Save any edits first." : "Cancel this order? Any deducted stock will be restored."}`,
          )
        )
          busy(button, async () => {
            const result = await api(`orders/${order.id}/${action}`, "POST");
            message("Order " + result.status.toLowerCase() + ".");
            await orderEditor(result);
          });
      };
  }
}
async function showReports() {
  content.onclick = null;
  content.innerHTML = `<div class="panel"><form id="report-form" class="toolbar"><label>Report<select name="kind"><option value="customers">Customer sales</option><option value="products">Product sales</option><option value="low-stock">Low stock</option><option value="movements">Stock movement history</option></select></label><label>From (customer sales)<input name="start" type="date"></label><label>To (customer sales)<input name="end" type="date"></label><label>Stock threshold<input name="threshold" type="number" min="0" step="1" value="10"></label><button>Run report</button></form><p class="muted">Sales include confirmed orders only. Customer sales are after discount. Product sales show gross item value.</p><div id="report"></div></div>`;
  const run = async () => {
    const data = new FormData(document.querySelector("#report-form"));
    const kind = data.get("kind");
    data.delete("kind");
    const result = await api(`reports/${kind}?${new URLSearchParams(data)}`);
    const columns = Object.keys(result.items[0] || {}).map((key) => [
      key,
      key.replaceAll("_", " "),
    ]);
    document.querySelector("#report").innerHTML = table(result.items, columns);
  };
  document.querySelector("#report-form").onsubmit = (event) => {
    event.preventDefault();
    busy(event.submitter, run);
  };
  await run();
}
function showImport() {
  content.onclick = null;
  content.innerHTML =
    '<div class="panel"><h2>Upload product CSV</h2><p class="muted">UTF-8 CSV · Maximum 2 MB. Every row must pass validation before anything is imported.</p><p>Columns in order</p><code>product_code,product_name,category,price,stock_quantity,status</code><form id="upload"><label>CSV file<input name="file" type="file" accept=".csv" required></label><button>Validate and import</button></form></div>';
  document.querySelector("#upload").onsubmit = (event) => {
    event.preventDefault();
    busy(event.submitter, async () => {
      const result = await api(
        "products/import",
        "POST",
        new FormData(event.target),
      );
      message(
        `${result.imported} products imported with opening stock records.`,
      );
      event.target.reset();
    });
  };
}
initialize().catch((error) => message(error.message, true));
