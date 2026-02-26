# Driver Backend API Documentation

**Version:** 1.0.0
**Base URL:** `/api/v1`
**Framework:** FastAPI (Python)
**Auth:** JWT Bearer Token (Authorization: `Bearer <token>`)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [System](#2-system)
3. [Drivers](#3-drivers)
4. [Invoices](#4-invoices)
5. [Routes](#5-routes)
6. [Branches](#6-branches)
7. [Admins](#7-admins)
8. [Customer Visits & Groups](#8-customer-visits--groups)
9. [PDF Operations](#9-pdf-operations)
10. [File Upload](#10-file-upload)
11. [Roles & Permissions](#11-roles--permissions)
12. [Error Responses](#12-error-responses)

---

## 1. Authentication

### POST `/api/v1/login`

Login with email and password to receive a JWT token.

**Access:** Public

**Request Body:**

```json
{
  "username": "user@example.com",
  "password": "yourpassword"
}
```

**Response `200`:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "role": "driver",
    "branches": ["Branch A", "Branch B"],
    "is_active": true
  }
}
```

**Errors:**

- `401` – Invalid credentials

---

### POST `/api/v1/logout`

Logout the currently authenticated user.

**Access:** Authenticated

**Response `200`:**

```json
{
  "message": "Logged out successfully"
}
```

---

### POST `/api/v1/refresh`

Refresh the JWT access token.

**Access:** Authenticated

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "role": "driver",
  "branch_id": 2
}
```

---

### GET `/api/v1/me`

Get the currently authenticated user's details.

**Access:** Authenticated

**Response `200`:**

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "role": "driver",
  "branches": ["Branch A"],
  "is_active": true
}
```

---

### POST `/api/v1/register`

Register a new user (admin or driver).

**Access:** Admin, Super Admin

**Request Body:**

```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "securepass",
  "role": "driver",
  "branch_id": 1
}
```

> `role` must be `"admin"` or `"driver"`. Admins cannot create `super_admin` accounts.

**Response `201`:**

```json
{
  "id": 2,
  "email": "jane@example.com",
  "name": "Jane Doe",
  "role": "driver",
  "branches": ["Branch A"],
  "is_active": true
}
```

**Errors:**

- `400` – Email already exists
- `403` – Insufficient permissions to assign role

---

## 2. System

### GET `/`

Root health/info endpoint.

**Access:** Public

**Response `200`:**

```json
{
  "message": "Pharma Delivery Backend API",
  "version": "1.0.0"
}
```

---

### GET `/health`

Check system and database health.

**Access:** Public

**Response `200`:**

```json
{
  "status": "ok",
  "database": "connected",
  "database_type": "postgresql",
  "super_admin_exists": true,
  "database_file_exists": true,
  "database_file_path": "/path/to/db"
}
```

**Response (error state):**

```json
{
  "status": "error",
  "database": "disconnected",
  "error": "Connection refused"
}
```

---

## 3. Drivers

### GET `/api/v1/drivers`

List all drivers with optional branch filtering and pagination.

**Access:** Admin, Super Admin

**Query Parameters:**

| Param      | Type    | Default | Description           |
| ---------- | ------- | ------- | --------------------- |
| `branch`   | string  | —       | Filter by branch name |
| `page`     | integer | `1`     | Page number           |
| `per_page` | integer | `20`    | Results per page      |

**Response `200`:**

```json
{
  "drivers": [
    {
      "id": 1,
      "username": "driver@example.com",
      "driver_name": "John Driver",
      "branches": ["Branch A"],
      "role": "driver",
      "isActive": true,
      "isTemporary": false,
      "created_at": "2024-01-15T10:00:00",
      "temp_password": null
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 3,
    "total_count": 45,
    "per_page": 20
  }
}
```

---

### POST `/api/v1/drivers`

Create a new permanent driver.

**Access:** Admin, Super Admin

**Request Body:**

```json
{
  "driver_name": "John Driver",
  "email": "john@example.com",
  "password": "securepass123",
  "branch_ids": [1, 2],
  "isTemporary": false
}
```

**Response `201`:**

```json
{
  "message": "Driver created successfully",
  "driver": {
    "id": 3,
    "username": "john@example.com",
    "driver_name": "John Driver",
    "branches": ["Branch A", "Branch B"],
    "role": "driver",
    "isActive": true,
    "isTemporary": false,
    "created_at": "2024-01-15T10:00:00"
  }
}
```

**Errors:**

- `400` – Email already exists
- `404` – Branch not found

---

### POST `/api/v1/drivers/temporary`

Create a temporary driver with auto-generated credentials.

**Access:** Admin, Super Admin

**Request Body:**

```json
{
  "branch_ids": [1, 2]
}
```

**Response `201`:**

```json
{
  "message": "Temporary driver created successfully",
  "driver": {
    "id": 4,
    "username": "temp_driver_a1b2@example.com",
    "driver_name": "Temporary Driver",
    "branches": ["Branch A"],
    "role": "driver",
    "isActive": true,
    "isTemporary": true,
    "created_at": "2024-01-15T10:00:00"
  },
  "credentials": {
    "username": "temp_driver_a1b2@example.com",
    "password": "auto_generated_password"
  }
}
```

---

### PUT `/api/v1/drivers/{driver_id}`

Update an existing driver's details.

**Access:** Admin, Super Admin

**Path Parameters:**

| Param       | Type    | Description      |
| ----------- | ------- | ---------------- |
| `driver_id` | integer | Driver's user ID |

**Request Body (all fields optional):**

```json
{
  "driver_name": "Updated Name",
  "email": "newemail@example.com",
  "branch_ids": [1, 3]
}
```

**Response `200`:**

```json
{
  "id": 3,
  "username": "newemail@example.com",
  "driver_name": "Updated Name",
  "branches": ["Branch A", "Branch C"],
  "role": "driver",
  "isActive": true,
  "isTemporary": false,
  "created_at": "2024-01-15T10:00:00"
}
```

**Errors:**

- `400` – Email already in use
- `404` – Driver or branch not found

---

### DELETE `/api/v1/drivers/{driver_id}`

Delete a driver by ID.

**Access:** Admin, Super Admin

**Path Parameters:**

| Param       | Type    | Description      |
| ----------- | ------- | ---------------- |
| `driver_id` | integer | Driver's user ID |

**Response `200`:**

```json
{
  "message": "Driver deleted successfully",
  "driver_id": 3,
  "driver_name": "John Driver",
  "driver_type": "permanent"
}
```

---

## 4. Invoices

### GET `/api/v1/invoices`

List invoices with filters and pagination.

**Access:** Driver (own invoices), Admin (branch invoices), Super Admin (requires `branch_id`)

**Query Parameters:**

| Param           | Type    | Description                               |
| --------------- | ------- | ----------------------------------------- |
| `branch_id`     | integer | Branch filter (required for super_admin)  |
| `status_filter` | string  | `"pending"` or `"delivered"`              |
| `search`        | string  | Search by customer name or invoice number |
| `from_date`     | string  | Start date filter `YYYY-MM-DD`            |
| `to_date`       | string  | End date filter `YYYY-MM-DD`              |
| `driver_id`     | integer | Filter by driver (admin/super_admin only) |
| `route_number`  | integer | Filter by route number                    |
| `route_date`    | string  | Filter by route date `YYYY-MM-DD`         |
| `page`          | integer | Page number (default: `1`)                |
| `per_page`      | integer | Results per page (default: `20`)          |

**Response `200`:**

```json
{
  "invoices": [
    {
      "invoice_id": 1,
      "cust_name": "Pharmacy Plus",
      "n_inv_no": "INV-2024-001",
      "amount": 1250.5,
      "invoice_date": "2024-01-15",
      "branch_id": 1,
      "assigned_driver_id": 3,
      "status": "pending",
      "pdf_path": null,
      "driver_signature": null,
      "driver_notes": null,
      "acknowledged_at": null,
      "delivery_date": null,
      "route_number": 1,
      "route_name": "Morning Route",
      "route_date": "2024-01-15",
      "customer_visit_group": "1-Pharmacy Plus-2024-01-15",
      "created_at": "2024-01-15T08:00:00",
      "updated_at": "2024-01-15T08:00:00"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 2,
    "total_count": 30,
    "per_page": 20
  }
}
```

---

### GET `/api/v1/invoices/{invoice_id}`

Get a single invoice by ID.

**Access:** Driver (own invoices only), Admin, Super Admin

**Path Parameters:**

| Param        | Type    | Description |
| ------------ | ------- | ----------- |
| `invoice_id` | integer | Invoice ID  |

**Response `200`:**

```json
{
  "invoice_id": 1,
  "cust_name": "Pharmacy Plus",
  "n_inv_no": "INV-2024-001",
  "amount": 1250.5,
  "invoice_date": "2024-01-15",
  "branch_id": 1,
  "assigned_driver_id": 3,
  "status": "pending",
  "pdf_path": null,
  "driver_signature": null,
  "driver_notes": null,
  "acknowledged_at": null,
  "delivery_date": null,
  "route_number": 1,
  "route_name": "Morning Route",
  "route_date": "2024-01-15",
  "customer_visit_group": "1-Pharmacy Plus-2024-01-15",
  "created_at": "2024-01-15T08:00:00",
  "updated_at": "2024-01-15T08:00:00"
}
```

**Errors:**

- `403` – Invoice not assigned to this driver
- `404` – Invoice not found

---

### POST `/api/v1/invoices/{invoice_id}/acknowledge`

Acknowledge a single invoice with a signature.

**Access:** Driver (owner only)

**Path Parameters:**

| Param        | Type    | Description |
| ------------ | ------- | ----------- |
| `invoice_id` | integer | Invoice ID  |

**Form Data (multipart/form-data):**

| Field            | Type         | Required | Description              |
| ---------------- | ------------ | -------- | ------------------------ |
| `signature_file` | file (PNG)   | Yes      | Driver's signature image |
| `notes`          | string       | No       | Optional delivery notes  |
| `photo_file`     | file (image) | No       | Optional delivery photo  |

**Response `200`:**

```json
{
  "message": "Invoice acknowledged and PDF generated successfully",
  "invoice_id": "1",
  "acknowledged_at": "2024-01-15T14:30:00",
  "pdf_url": "/pdfs/invoice_1_acknowledged.pdf"
}
```

**Errors:**

- `400` – Invoice already acknowledged or invalid signature
- `403` – Invoice not assigned to this driver
- `404` – Invoice not found

---

### POST `/api/v1/invoices/upload-csv`

Upload a CSV file to bulk-create invoices and assign to a driver.

**Access:** Admin (must have branch assigned)

**Query Parameters:**

| Param        | Type    | Required | Description                  |
| ------------ | ------- | -------- | ---------------------------- |
| `driver_id`  | integer | Yes      | Driver to assign invoices to |
| `route_name` | string  | No       | Custom name for this route   |

**Form Data (multipart/form-data):**

| Field  | Type       | Required | Description                |
| ------ | ---------- | -------- | -------------------------- |
| `file` | file (CSV) | Yes      | CSV file with invoice data |

**CSV Required Columns:**

| Column       | Description                         |
| ------------ | ----------------------------------- |
| `cust_name`  | Customer name                       |
| `amount`     | Invoice amount (decimal)            |
| `n_inv_no`   | Invoice number                      |
| `d_inv_date` | Invoice date (DD/MM/YYYY, optional) |

**Response `200`:**

```json
{
  "message": "Successfully uploaded 15 invoices for Route 3",
  "uploaded_count": 15,
  "skipped_count": 2
}
```

> Duplicate invoices (same `n_inv_no`) are skipped. Routes are numbered sequentially per driver per day.

**Errors:**

- `400` – Invalid CSV format, missing columns, or invalid driver
- `403` – Admin does not have a branch assigned
- `404` – Driver not found

---

### GET `/api/v1/invoices-grouped`

Get driver's invoices grouped by customer visit group (optimized for driver view).

**Access:** Driver

**Query Parameters:**

| Param          | Type    | Description                  |
| -------------- | ------- | ---------------------------- |
| `route_number` | integer | Filter by route number       |
| `status`       | string  | `"pending"` or `"delivered"` |
| `search`       | string  | Search by customer name      |
| `created_date` | string  | Filter by date `YYYY-MM-DD`  |

**Response `200`:**

```json
{
  "groups": [
    {
      "customer_visit_group": "1-Pharmacy Plus-2024-01-15",
      "customer_name": "Pharmacy Plus",
      "shop_address": "123 Main St",
      "route_number": 1,
      "route_name": "Morning Route",
      "route_display": "Route 1: Morning Route",
      "invoice_count": 3,
      "total_amount": 3750.0,
      "status": "pending",
      "first_invoice_id": 1,
      "invoice_numbers": ["INV-001", "INV-002", "INV-003"],
      "sequence_order": 1,
      "branch": "Branch A"
    }
  ],
  "total_groups": 8,
  "pending_groups": 5,
  "delivered_groups": 3
}
```

---

### GET `/api/v1/customer-group/{group_id}`

Get all invoices in a specific customer visit group.

**Access:** Driver

**Path Parameters:**

| Param      | Type   | Description                                                         |
| ---------- | ------ | ------------------------------------------------------------------- |
| `group_id` | string | Customer visit group identifier (e.g. `1-Pharmacy Plus-2024-01-15`) |

**Response `200`:**

```json
{
  "customer_visit_group": "1-Pharmacy Plus-2024-01-15",
  "customer_name": "Pharmacy Plus",
  "route_number": 1,
  "route_name": "Morning Route",
  "route_display": "Route 1: Morning Route",
  "invoices": [ ...InvoiceInfo ],
  "total_amount": 3750.00,
  "invoice_count": 3,
  "all_acknowledged": false,
  "branch": "Branch A"
}
```

---

### POST `/api/v1/acknowledge-group/{group_id}`

Acknowledge all invoices in a group with a single signature.

**Access:** Driver

**Path Parameters:**

| Param      | Type   | Description                     |
| ---------- | ------ | ------------------------------- |
| `group_id` | string | Customer visit group identifier |

**Form Data (multipart/form-data):**

| Field       | Type       | Required | Description              |
| ----------- | ---------- | -------- | ------------------------ |
| `signature` | file (PNG) | Yes      | Driver's signature image |
| `notes`     | string     | No       | Optional delivery notes  |

**Response `200`:**

```json
{
  "message": "Successfully acknowledged 3 invoices for Pharmacy Plus",
  "customer_name": "Pharmacy Plus",
  "acknowledged_invoices": ["INV-001", "INV-002", "INV-003"],
  "signature_saved": "uploads/signatures/sig_1234.png",
  "pdfs_generated": [
    "pdfs/invoice_1_acknowledged.pdf",
    "pdfs/invoice_2_acknowledged.pdf",
    "pdfs/invoice_3_acknowledged.pdf"
  ]
}
```

---

## 5. Routes

### GET `/api/v1/routes`

List all routes with optional filters.

**Access:** Admin (own branch only), Super Admin (all branches)

**Query Parameters:**

| Param        | Type    | Description                      |
| ------------ | ------- | -------------------------------- |
| `driver_id`  | integer | Filter by driver                 |
| `route_date` | string  | Filter by date `YYYY-MM-DD`      |
| `page`       | integer | Page number (default: `1`)       |
| `per_page`   | integer | Results per page (default: `20`) |

**Response `200`:**

```json
{
  "routes": [
    {
      "route_number": 1,
      "route_name": "Morning Route",
      "route_display": "Route 1: Morning Route (2024-01-15)",
      "invoice_count": 10,
      "driver_name": "John Driver",
      "created_date": "2024-01-15"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 2,
    "total_count": 25,
    "per_page": 20
  }
}
```

---

### GET `/api/v1/driver-routes`

Get routes for the currently authenticated driver.

**Access:** Driver

**Query Parameters:**

| Param        | Type   | Description                 |
| ------------ | ------ | --------------------------- |
| `route_date` | string | Filter by date `YYYY-MM-DD` |

**Response `200`:** Same structure as `GET /api/v1/routes`

---

### GET `/api/v1/available-routes`

Get available routes for a specific date.

**Access:** Driver, Admin, Super Admin

**Query Parameters:**

| Param        | Type    | Required | Description            |
| ------------ | ------- | -------- | ---------------------- |
| `route_date` | string  | Yes      | Date `YYYY-MM-DD`      |
| `driver_id`  | integer | No       | Admin/Super Admin only |

**Response `200`:** Same structure as `GET /api/v1/routes`

---

### GET `/api/v1/admin/available-routes`

Get available routes for a specific driver and date (admin view).

**Access:** Admin, Super Admin

**Query Parameters:**

| Param        | Type    | Required | Description       |
| ------------ | ------- | -------- | ----------------- |
| `driver_id`  | integer | Yes      | Driver ID         |
| `route_date` | string  | Yes      | Date `YYYY-MM-DD` |

**Response `200`:** Same structure as `GET /api/v1/routes`

---

## 6. Branches

### GET `/api/v1/branches`

List all branches with pagination.

**Access:** Admin, Super Admin

**Query Parameters:**

| Param      | Type    | Default | Description      |
| ---------- | ------- | ------- | ---------------- |
| `page`     | integer | `1`     | Page number      |
| `per_page` | integer | `20`    | Results per page |

**Response `200`:**

```json
{
  "branches": [
    {
      "id": "1",
      "name": "Head Office",
      "city": "Mumbai",
      "phone": "+91-9876543210",
      "email": "headoffice@company.com",
      "created_at": "2024-01-01T00:00:00",
      "is_active": true
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 5,
    "per_page": 20
  }
}
```

---

### POST `/api/v1/branches`

Create a new branch.

**Access:** Super Admin only

**Request Body:**

```json
{
  "name": "South Branch",
  "city": "Chennai",
  "phone": "+91-9876543211",
  "email": "south@company.com"
}
```

> `phone` is optional.

**Response `201`:**

```json
{
  "id": "2",
  "name": "South Branch",
  "city": "Chennai",
  "phone": "+91-9876543211",
  "email": "south@company.com",
  "created_at": "2024-01-15T10:00:00",
  "is_active": true
}
```

**Errors:**

- `400` – Email already exists

---

### GET `/api/v1/branches/{branch_name}/details`

Get detailed information about a branch including its users.

**Access:** Admin, Super Admin

**Path Parameters:**

| Param         | Type   | Description                         |
| ------------- | ------ | ----------------------------------- |
| `branch_name` | string | Branch name (URL-encoded if needed) |

**Response `200`:**

```json
{
  "branch": {
    "id": "1",
    "name": "Head Office",
    "city": "Mumbai",
    "phone": "+91-9876543210",
    "email": "headoffice@company.com",
    "created_at": "2024-01-01T00:00:00",
    "is_active": true
  },
  "users": {
    "admins": [
      {
        "id": 1,
        "name": "Admin User",
        "email": "admin@company.com",
        "role": "admin",
        "branch": "Head Office"
      }
    ],
    "drivers": [
      {
        "id": 3,
        "driver_name": "John Driver",
        "username": "john@company.com",
        "branches": ["Head Office"],
        "isTemporary": false
      }
    ],
    "total_users": 6
  }
}
```

---

## 7. Admins

### GET `/api/v1/admins`

List all admin users.

**Access:** Super Admin only

**Query Parameters:**

| Param      | Type    | Default | Description      |
| ---------- | ------- | ------- | ---------------- |
| `page`     | integer | `1`     | Page number      |
| `per_page` | integer | `20`    | Results per page |

**Response `200`:**

```json
{
  "admins": [
    {
      "id": 1,
      "name": "Admin User",
      "email": "admin@company.com",
      "role": "admin",
      "branch": "Head Office",
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 3,
    "per_page": 20
  }
}
```

---

### POST `/api/v1/admins`

Create a new admin user.

**Access:** Super Admin only

**Request Body:**

```json
{
  "name": "New Admin",
  "email": "newadmin@company.com",
  "password": "securepass123",
  "branch_id": "1"
}
```

**Response `201`:**

```json
{
  "message": "Admin created successfully",
  "admin": {
    "id": 2,
    "name": "New Admin",
    "email": "newadmin@company.com",
    "role": "admin",
    "branch": "Head Office",
    "created_at": "2024-01-15T10:00:00"
  }
}
```

---

### PUT `/api/v1/admins/{admin_id}`

Update an admin user's details.

**Access:** Super Admin only

**Path Parameters:**

| Param      | Type    | Description     |
| ---------- | ------- | --------------- |
| `admin_id` | integer | Admin's user ID |

**Request Body (all fields optional):**

```json
{
  "name": "Updated Admin Name",
  "email": "updated@company.com",
  "password": "newpassword",
  "branch_id": "2"
}
```

**Response `200`:**

```json
{
  "id": 2,
  "name": "Updated Admin Name",
  "email": "updated@company.com",
  "role": "admin",
  "branch": "South Branch",
  "created_at": "2024-01-15T10:00:00"
}
```

---

### DELETE `/api/v1/admins/{admin_id}`

Delete an admin user.

**Access:** Super Admin only

**Path Parameters:**

| Param      | Type    | Description     |
| ---------- | ------- | --------------- |
| `admin_id` | integer | Admin's user ID |

**Response `200`:**

```json
{
  "message": "Admin deleted successfully",
  "admin_id": 2,
  "admin_name": "Updated Admin Name"
}
```

---

## 8. Customer Visits & Groups

### GET `/api/v1/customer-visits`

List all customer visits (invoices grouped by customer + route + date) for the driver.

**Access:** Driver

**Query Parameters:**

| Param          | Type    | Description                      |
| -------------- | ------- | -------------------------------- |
| `route_date`   | string  | Filter by date `YYYY-MM-DD`      |
| `route_number` | integer | Filter by route number           |
| `page`         | integer | Page number (default: `1`)       |
| `per_page`     | integer | Results per page (default: `20`) |

**Response `200`:**

```json
{
  "visits": [
    {
      "customer_name": "Pharmacy Plus",
      "route_number": 1,
      "route_name": "Morning Route",
      "route_display": "Route 1: Morning Route",
      "route_date": "2024-01-15",
      "invoice_count": 3,
      "total_amount": 3750.0,
      "acknowledged_count": 0,
      "is_fully_acknowledged": false,
      "invoice_ids": [1, 2, 3]
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 2,
    "total_count": 25,
    "per_page": 20
  }
}
```

---

### GET `/api/v1/customer-visits/{customer_name}/{route_number}/{route_date}`

Get details for a specific customer visit.

**Access:** Driver

**Path Parameters:**

| Param           | Type    | Description                 |
| --------------- | ------- | --------------------------- |
| `customer_name` | string  | Customer name (URL-encoded) |
| `route_number`  | integer | Route number                |
| `route_date`    | string  | Date `YYYY-MM-DD`           |

**Response `200`:**

```json
{
  "customer_name": "Pharmacy Plus",
  "route_display": "Route 1: Morning Route",
  "route_date": "2024-01-15",
  "total_amount": 3750.00,
  "acknowledged_count": 1,
  "total_count": 3,
  "invoices": [ ...InvoiceInfo ]
}
```

---

### POST `/api/v1/customer-visits/{customer_name}/{route_number}/{route_date}/acknowledge`

Acknowledge all invoices for a specific customer visit with a single signature.

**Access:** Driver

**Path Parameters:**

| Param           | Type    | Description                 |
| --------------- | ------- | --------------------------- |
| `customer_name` | string  | Customer name (URL-encoded) |
| `route_number`  | integer | Route number                |
| `route_date`    | string  | Date `YYYY-MM-DD`           |

**Form Data (multipart/form-data):**

| Field            | Type       | Required | Description              |
| ---------------- | ---------- | -------- | ------------------------ |
| `signature_file` | file (PNG) | Yes      | Driver's signature image |
| `notes`          | string     | No       | Optional delivery notes  |

**Response `200`:**

```json
{
  "message": "Successfully acknowledged 3 invoices for Pharmacy Plus",
  "customer_name": "Pharmacy Plus",
  "acknowledged_invoices": ["1", "2", "3"],
  "acknowledged_at": "2024-01-15T14:30:00"
}
```

---

## 9. PDF Operations

### GET `/api/v1/invoices/{invoice_id}/download-pdf`

Download a PDF for an acknowledged invoice (as attachment).

**Access:** Driver (own invoices), Admin, Super Admin

**Path Parameters:**

| Param        | Type    | Description |
| ------------ | ------- | ----------- |
| `invoice_id` | integer | Invoice ID  |

**Response `200`:** PDF file (`application/pdf`, `Content-Disposition: attachment`)

**Errors:**

- `400` – Invoice not yet acknowledged
- `404` – PDF not found

---

### GET `/api/v1/invoices/{invoice_id}/preview-pdf`

Preview a PDF inline in the browser.

**Access:** Driver (own invoices), Admin, Super Admin

**Response `200`:** PDF file (`application/pdf`, `Content-Disposition: inline`)

---

### GET `/api/v1/admin/invoices/{invoice_id}/download-pdf`

Download a PDF (admin-only route).

**Access:** Admin, Super Admin

**Response `200`:** PDF file (`application/pdf`, `Content-Disposition: attachment`)

---

### GET `/api/v1/admin/invoices/{invoice_id}/preview-pdf`

Preview a PDF inline (admin-only route).

**Access:** Admin, Super Admin

**Response `200`:** PDF file (`application/pdf`, `Content-Disposition: inline`)

---

### POST `/api/v1/bulk-download-pdfs`

Download multiple PDFs as a ZIP archive.

**Access:** Admin, Super Admin

**Request Body:**

```json
{
  "invoice_ids": [1, 2, 3, 4, 5]
}
```

> Maximum 100 invoices per request. Only acknowledged invoices are included.

**Response `200`:** ZIP file (`application/zip`) containing:

- Individual PDF files for each acknowledged invoice
- `missing_pdfs_report.txt` if any PDFs could not be generated

**Errors:**

- `400` – No IDs provided or exceeds 100 invoice limit
- `404` – Invoice not found

---

### POST `/api/v1/route-wise-pdf`

Generate a route summary PDF with invoice table and totals.

**Access:** Admin, Super Admin

**Request Body (all fields optional):**

```json
{
  "route_name": "Route 1",
  "driver_id": 3,
  "date": "2024-01-15",
  "branch_id": 1
}
```

**Response `200`:** PDF file (`application/pdf`) with:

- Invoice table (customer, invoice number, amount, status)
- Driver signatures
- Route totals

**Errors:**

- `404` – No invoices found matching filters
- `500` – PDF generation error

---

## 10. File Upload

### POST `/api/v1/files/upload`

Upload a general-purpose file (e.g. images, documents).

**Access:** Admin, Super Admin

**Form Data (multipart/form-data):**

| Field       | Type   | Required | Description                          |
| ----------- | ------ | -------- | ------------------------------------ |
| `file`      | file   | Yes      | File to upload                       |
| `file_type` | string | No       | File category (default: `"general"`) |

**Response `200`:**

```json
{
  "message": "File uploaded successfully",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_url": "http://example.com/uploads/550e8400.pdf",
  "file_name": "document.pdf",
  "file_size": 204800
}
```

---

## 11. Roles & Permissions

| Endpoint                              | Driver   | Admin       | Super Admin              |
| ------------------------------------- | -------- | ----------- | ------------------------ |
| Login / Logout / Me / Refresh         | ✓        | ✓           | ✓                        |
| GET /invoices                         | Own only | Branch only | All (requires branch_id) |
| POST /invoices/{id}/acknowledge       | Own only | —           | —                        |
| GET /invoices-grouped                 | ✓        | —           | —                        |
| GET /customer-visits                  | ✓        | —           | —                        |
| POST /customer-visits/.../acknowledge | ✓        | —           | —                        |
| POST /acknowledge-group/{group_id}    | ✓        | —           | —                        |
| GET /dashboard, /profile              | ✓        | —           | —                        |
| GET /driver-routes                    | ✓        | —           | —                        |
| GET /available-routes                 | ✓        | ✓           | ✓                        |
| GET /admin/available-routes           | —        | ✓           | ✓                        |
| GET /routes                           | —        | Branch only | ✓                        |
| POST /invoices/upload-csv             | —        | ✓           | ✓                        |
| POST /route-wise-pdf                  | —        | ✓           | ✓                        |
| POST /bulk-download-pdfs              | —        | ✓           | ✓                        |
| GET /admin/invoices/.../pdf           | —        | ✓           | ✓                        |
| GET /drivers                          | —        | ✓           | ✓                        |
| POST /drivers                         | —        | ✓           | ✓                        |
| PUT /drivers/{id}                     | —        | ✓           | ✓                        |
| DELETE /drivers/{id}                  | —        | ✓           | ✓                        |
| GET /branches                         | —        | ✓           | ✓                        |
| POST /branches                        | —        | —           | ✓                        |
| GET /branches/{name}/details          | —        | ✓           | ✓                        |
| GET /admins                           | —        | —           | ✓                        |
| POST /admins                          | —        | —           | ✓                        |
| PUT /admins/{id}                      | —        | —           | ✓                        |
| DELETE /admins/{id}                   | —        | —           | ✓                        |
| POST /files/upload                    | —        | ✓           | ✓                        |
| GET /                                 | ✓        | ✓           | ✓                        |
| GET /health                           | ✓        | ✓           | ✓                        |

---

## 12. Error Responses

All errors follow standard HTTP status codes with a JSON body:

```json
{
  "detail": "Error description here"
}
```

### Common Error Codes

| Status | Meaning                                                                  |
| ------ | ------------------------------------------------------------------------ |
| `400`  | Bad Request – Invalid input, duplicate data, or business logic violation |
| `401`  | Unauthorized – Missing or invalid JWT token                              |
| `403`  | Forbidden – Valid token but insufficient permissions                     |
| `404`  | Not Found – Resource does not exist                                      |
| `422`  | Unprocessable Entity – Request body validation failed                    |
| `500`  | Internal Server Error – Unexpected server-side error                     |

### Validation Error Example (`422`)

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Invoice Status Reference

| Status      | Description                            |
| ----------- | -------------------------------------- |
| `pending`   | Assigned to driver, not yet delivered  |
| `delivered` | Acknowledged by driver (PDF generated) |

---

## Invoice `customer_visit_group` Format

Groups are identified by a string in the format:

```
{route_number}-{customer_name}-{route_date}
```

Example: `1-Pharmacy Plus-2024-01-15`

---

## Static File Paths

| Path                  | Description                    |
| --------------------- | ------------------------------ |
| `/pdfs/{filename}`    | Acknowledged invoice PDFs      |
| `/uploads/{filename}` | Uploaded signatures and images |

---

_Generated for Driver Backend v1.0.0_
