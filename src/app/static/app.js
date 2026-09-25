const API = "http://localhost:8000";

const headers = {
    "Content-Type": "application/json",
    "X-API-Key": "minipay-key"
};

async function request(url, options = {}) {

    options.headers = headers;

    const response = await fetch(API + url, options);

    const data = await response.json();

    document.getElementById("result").textContent =
        JSON.stringify({
            status: response.status,
            data: data
        }, null, 2);
}


function createCustomer() {

    request("/api/customers", {
        method: "POST",
        body: JSON.stringify({
            customer_ref:
                document.getElementById("customerRef").value,

            name:
                document.getElementById("customerName").value
        })
    });
}


function createPayment() {

    request("/api/payments", {
        method: "POST",
        body: JSON.stringify({
            transaction_ref:
                document.getElementById("transactionRef").value,

            customer_id:
                Number(document.getElementById("customerId").value),

            amount:
                Number(document.getElementById("amount").value)
        })
    });
}


function getPayment() {

    const id =
        document.getElementById("paymentId").value;

    request(`/api/payments/${id}`);
}


function getCustomerPayments() {

    const id =
        document.getElementById("paymentsCustomerId").value;

    request(`/api/customers/${id}/payments`);
}