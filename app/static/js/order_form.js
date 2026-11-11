// Order form and order detail page behaviour (vanilla JS).
// Totals shown here are display only: the server recalculates everything from its own prices.

(function () {
  "use strict";

  // ---- Section 1: small helpers used by both pages ----

  // 1234.5 -> "1234.50"
  function formatMoney(number) {
    return Number(number).toFixed(2);
  }

  // Always resolves with { httpStatus, data } and never throws, so callers decide what to show.
  function fetchJSON(url, method) {
    return fetch(url, {
      method: method || "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    }).then(function (response) {
      return response.json().then(function (data) {
        return { httpStatus: response.status, data: data };
      });
    }).catch(function () {
      // Network failure or non-JSON reply.
      return { httpStatus: 0, data: { ok: false, message: "Could not reach the server. Please try again." } };
    });
  }

  // Show a message in the <div id="js-message"> box. kind = "success" | "error".
  function showMessage(text, kind) {
    var box = document.getElementById("js-message");
    if (!box) { return; }
    box.textContent = text;
    box.className = "flash flash-" + kind;
    box.hidden = false;
  }

  function hideMessage() {
    var box = document.getElementById("js-message");
    if (box) { box.hidden = true; }
  }

  // Show or clear the text in the field's <span class="field-error" data-error-for="...">.
  function setFieldError(name, text, rowElement) {
    var scope = rowElement || document;
    var span = scope.querySelector('.field-error[data-error-for="' + name + '"]');
    if (!span) { return; }
    span.textContent = text;
    span.hidden = (text === "");
  }

  // Disable a button and remember its label so we can restore it later.
  function setBusy(button, busyLabel) {
    if (!button) { return; }
    button.dataset.originalLabel = button.textContent;
    button.textContent = busyLabel;
    button.disabled = true;
  }

  function setIdle(button) {
    if (!button) { return; }
    if (button.dataset.originalLabel) {
      button.textContent = button.dataset.originalLabel;
    }
    button.disabled = false;
  }

  // ---- Section 2: the order form (new / edit) ----

  function setUpOrderForm(form) {
    // Product list embedded by the server (names only); price and stock are fetched per product.
    var products = JSON.parse(document.getElementById("products-data").textContent);
    var initialRows = JSON.parse(document.getElementById("rows-data").textContent);

    var itemsBody = document.getElementById("items-body");
    var addButton = document.getElementById("add-item");
    var discountInput = document.getElementById("discount_percentage");
    var customerSelect = document.getElementById("customer_id");
    var saveButton = form.querySelector('button[type="submit"]');

    // Cache of fetched product details so the same product is not requested twice.
    var productInfo = {};

    // ---- building a row -----------------------------------------------------

    function buildProductSelect(selectedId) {
      var select = document.createElement("select");
      select.name = "product_id";

      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "Choose a product";
      select.appendChild(blank);

      for (var i = 0; i < products.length; i++) {
        var option = document.createElement("option");
        option.value = products[i].id;
        option.textContent = products[i].product_code + " - " + products[i].name;
        if (String(products[i].id) === String(selectedId)) {
          option.selected = true;
        }
        select.appendChild(option);
      }
      return select;
    }

    function buildErrorSpan(forName) {
      var span = document.createElement("span");
      span.className = "field-error";
      span.dataset.errorFor = forName;
      span.hidden = true;
      return span;
    }

    function addRow(productId, quantity) {
      var row = document.createElement("tr");

      var productCell = document.createElement("td");
      var select = buildProductSelect(productId);
      productCell.appendChild(select);
      productCell.appendChild(buildErrorSpan("product_id"));

      var stockCell = document.createElement("td");
      stockCell.className = "num stock";
      var rateCell = document.createElement("td");
      rateCell.className = "num rate";

      var qtyCell = document.createElement("td");
      var qtyInput = document.createElement("input");
      qtyInput.type = "text";
      qtyInput.name = "quantity";
      qtyInput.inputMode = "numeric";
      qtyInput.className = "qty";
      qtyInput.value = quantity || "";
      qtyCell.appendChild(qtyInput);
      qtyCell.appendChild(buildErrorSpan("quantity"));

      var amountCell = document.createElement("td");
      amountCell.className = "num amount";

      var removeCell = document.createElement("td");
      var removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "btn-text btn-danger";
      removeButton.textContent = "Remove";
      removeButton.addEventListener("click", function () {
        itemsBody.removeChild(row);
        recalculate();
      });
      removeCell.appendChild(removeButton);

      row.appendChild(productCell);
      row.appendChild(stockCell);
      row.appendChild(rateCell);
      row.appendChild(qtyCell);
      row.appendChild(amountCell);
      row.appendChild(removeCell);
      itemsBody.appendChild(row);

      select.addEventListener("change", function () {
        loadProductIntoRow(row);
      });
      qtyInput.addEventListener("input", function () {
        validateRow(row);
        recalculate();
      });

      // Pre-filled row (edit page / after a server error): load its product now.
      if (select.value) {
        loadProductIntoRow(row);
      }
    }

    // ---- fetching price and stock -------------------------------------------

    function loadProductIntoRow(row) {
      var select = row.querySelector("select");
      var productId = select.value;

      if (!productId) {
        row.dataset.productLoaded = "";
        recalculate();
        return;
      }

      if (productInfo[productId]) {
        recalculate();
        validateRow(row);
        return;
      }

      row.querySelector(".rate").textContent = "...";
      row.querySelector(".stock").textContent = "...";

      fetchJSON("/api/products/" + productId).then(function (result) {
        if (result.data.ok) {
          productInfo[productId] = result.data;
        } else {
          // e.g. product deactivated between page load and now
          setFieldError("product_id", result.data.message || "Product not available.", row);
        }
        recalculate();
        validateRow(row);
      });
    }

    // ---- live totals --------------------------------------------------------

    function recalculate() {
      var subtotal = 0;
      var rows = itemsBody.querySelectorAll("tr");

      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var select = row.querySelector("select");
        if (!select) { continue; }   // skip the <noscript> fallback row

        var info = productInfo[select.value];
        var qty = parseInt(row.querySelector(".qty").value, 10);

        var rate = info ? Number(info.price) : 0;
        var amount = (info && qty > 0) ? qty * rate : 0;

        row.querySelector(".stock").textContent = info ? info.stock_quantity : "";
        row.querySelector(".rate").textContent = info ? formatMoney(rate) : "";
        row.querySelector(".amount").textContent = amount ? formatMoney(amount) : "";

        subtotal += amount;
      }

      var discountPct = parseFloat(discountInput.value) || 0;
      var discount = subtotal * discountPct / 100;

      document.getElementById("preview-subtotal").textContent = formatMoney(subtotal);
      document.getElementById("preview-discount").textContent = formatMoney(discount);
      document.getElementById("preview-total").textContent = formatMoney(subtotal - discount);
    }

    // ---- inline validation --------------------------------------------------
    // Mirrors the server's rules for quick feedback only; the server still validates everything.

    function validateRow(row) {
      var select = row.querySelector("select");
      var qtyInput = row.querySelector(".qty");
      var ok = true;

      setFieldError("product_id", "", row);
      setFieldError("quantity", "", row);

      if (!select.value) {
        setFieldError("product_id", "Choose a product.", row);
        ok = false;
      } else {
        var others = itemsBody.querySelectorAll("select");
        for (var i = 0; i < others.length; i++) {
          if (others[i] !== select && others[i].value === select.value) {
            setFieldError("product_id", "This product is already on the order.", row);
            ok = false;
            break;
          }
        }
      }

      var qtyText = qtyInput.value.trim();
      if (!/^[0-9]+$/.test(qtyText) || parseInt(qtyText, 10) <= 0) {
        setFieldError("quantity", "Enter a whole number above 0.", row);
        ok = false;
      } else {
        var info = productInfo[select.value];
        if (info && parseInt(qtyText, 10) > info.stock_quantity) {
          // Warning only: a draft may be saved before stock arrives; the server decides at confirm.
          setFieldError("quantity", "Only " + info.stock_quantity + " in stock.", row);
        }
      }
      return ok;
    }

    function validateForm() {
      var ok = true;
      hideMessage();

      setFieldError("customer_id", "");
      if (!customerSelect.value) {
        setFieldError("customer_id", "Choose a customer.");
        ok = false;
      }

      setFieldError("discount_percentage", "");
      var discount = parseFloat(discountInput.value || "0");
      if (isNaN(discount) || discount < 0 || discount > 20) {
        setFieldError("discount_percentage", "Discount must be between 0 and 20.");
        ok = false;
      }

      var rows = itemsBody.querySelectorAll("tr");
      var filledRows = 0;
      for (var i = 0; i < rows.length; i++) {
        if (!rows[i].querySelector("select")) { continue; }
        filledRows++;
        if (!validateRow(rows[i])) { ok = false; }
      }
      if (filledRows === 0) {
        showMessage("Add at least one item to the order.", "error");
        ok = false;
      }
      return ok;
    }

    // ---- wiring up ----------------------------------------------------------

    addButton.addEventListener("click", function () { addRow("", ""); });

    discountInput.addEventListener("input", function () {
      setFieldError("discount_percentage", "");
      recalculate();
    });

    customerSelect.addEventListener("change", function () {
      setFieldError("customer_id", "");
    });

    // Validate first, then disable Save so a double click cannot create two orders.
    form.addEventListener("submit", function (event) {
      if (!validateForm()) {
        event.preventDefault();
        showMessage("Please fix the highlighted fields.", "error");
        return;
      }
      setBusy(saveButton, "Saving...");
    });

    // Start with the saved / previously submitted rows, or one empty row.
    if (initialRows.length === 0) {
      addRow("", "");
    } else {
      for (var r = 0; r < initialRows.length; r++) {
        addRow(initialRows[r].product_id, initialRows[r].quantity);
      }
    }
    recalculate();
  }

  // ---- Section 3: the order detail page (Confirm / Cancel buttons) ----

  function setUpActionForms(forms) {
    // Each form: action = no-JS HTML route, data-api-url = JSON route, data-confirm-text = dialog text.
    var allButtons = [];
    for (var i = 0; i < forms.length; i++) {
      allButtons.push(forms[i].querySelector("button"));
    }

    function disableAll(busyButton, label) {
      for (var i = 0; i < allButtons.length; i++) {
        allButtons[i].disabled = true;
      }
      setBusy(busyButton, label);
    }

    function enableAll() {
      for (var i = 0; i < allButtons.length; i++) {
        setIdle(allButtons[i]);
      }
    }

    // Update the status badge and remove buttons that no longer apply, without a reload.
    function applyNewStatus(newStatus) {
      var badge = document.getElementById("order-status");
      if (badge) {
        badge.textContent = newStatus;
        badge.className = "badge status-" + newStatus.toLowerCase();
      }

      var editLink = document.getElementById("edit-link");
      if (editLink) { editLink.remove(); }

      for (var i = 0; i < forms.length; i++) {
        var action = forms[i].dataset.action;
        var keep = (newStatus === "Confirmed" && action === "cancel");
        if (!keep) { forms[i].remove(); }
      }
    }

    for (var f = 0; f < forms.length; f++) {
      (function (form) {
        form.addEventListener("submit", function (event) {
          event.preventDefault();   // we handle it with fetch instead

          if (!window.confirm(form.dataset.confirmText)) {
            return;                 // user clicked "Cancel" in the dialog
          }

          var button = form.querySelector("button");
          hideMessage();
          disableAll(button, "Please wait...");

          fetchJSON(form.dataset.apiUrl, "POST").then(function (result) {
            if (result.data.ok) {
              showMessage(result.data.message, "success");
              applyNewStatus(result.data.status);
            } else {
              // 409 business rule, 403 not your order, 404 unknown id, 401 session expired.
              showMessage(result.data.message || "Request failed.", "error");
              enableAll();
            }
          });
        });
      })(forms[f]);
    }
  }

  // ---- Start: decide which page we are on by what exists in the document. ----

  var orderForm = document.getElementById("order-form");
  if (orderForm) {
    setUpOrderForm(orderForm);
  }

  var actionForms = document.querySelectorAll("form[data-api-url]");
  if (actionForms.length > 0) {
    setUpActionForms(actionForms);
  }
})();
