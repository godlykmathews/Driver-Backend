# API Documentation

## Authentication

### Login

**POST** `/login`
Authenticate user and return access token.

**Request Body**

```json
{
  "username": "admin@example.com",
  "password": "password123"
}
```

**Response**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "1",
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "admin",
    "branches": ["Main Branch"],
    "is_active": true
  }
}
```

### Logout

**POST** `/logout`
Logout user.

**Response**

```json
{
  "message": "Logged out successfully"
}
```

### Register User

**POST** `/register`
Register a new user (Admin only).

**Request Body**

```json
{
  "name": "New User",
  "email": "user@example.com",
  "role": "driver",
  "branch_id": 1,
  "password": "password123"
}
```

**Response**

```json
{
  "user_id": 2,
  "name": "New User",
  "email": "user@example.com",
  "role": "driver",
  "branch_id": 1,
  "is_temporary": false,
  "created_at": "2023-01-01T12:00:00",
  "updated_at": "2023-01-01T12:00:00"
}
```

### Get Current User

**GET** `/me`
Get current user profile.

**Response**

```json
{
  "user_id": 1,
  "name": "Admin User",
  "email": "admin@example.com",
  "role": "admin",
  "branch_id": 1,
  "is_temporary": false,
  "created_at": "2023-01-01T12:00:00",
  "updated_at": "2023-01-01T12:00:00"
}
```

## Admin Operations

### Get Drivers

**GET** `/drivers`
Get list of drivers.

**Response**

```json
{
  "drivers": [
    {
      "id": "2",
      "username": "driver@example.com",
      "driver_name": "Driver Name",
      "branches": ["Main Branch"],
      "role": "driver",
      "isActive": true,
      "isTemporary": false,
      "created_at": "2023-01-01T12:00:00"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Create Driver

**POST** `/drivers`
Create a new driver.

**Request Body**

```json
{
  "driver_name": "Driver Name",
  "email": "driver@example.com",
  "password": "password123",
  "branch_ids": [1],
  "isTemporary": false
}
```

**Response**

```json
{
  "driver": {
    "id": "2",
    "username": "driver@example.com",
    "driver_name": "Driver Name",
    "branches": ["Main Branch"],
    "role": "driver",
    "isActive": true,
    "isTemporary": false,
    "created_at": "2023-01-01T12:00:00"
  },
  "message": "Driver created successfully"
}
```

### Create Temporary Driver

**POST** `/drivers/temporary`
Create a temporary driver.

**Request Body**

```json
{
  "branch_ids": [1]
}
```

**Response**

```json
{
  "driver": {
    "id": "3",
    "username": "temp_user_123",
    "driver_name": "Temporary Driver",
    "branches": ["Main Branch"],
    "role": "driver",
    "isActive": true,
    "isTemporary": true,
    "created_at": "2023-01-01T12:00:00"
  },
  "credentials": {
    "username": "temp_user_123",
    "password": "generated_password"
  },
  "message": "Temporary driver created"
}
```

### Upload Invoices CSV

**POST** `/invoices/upload-csv`
Upload invoices via CSV file.

**Request Body**
Multipart Form Data: `file` (CSV file)

**Response**

```json
{
  "message": "Upload successful",
  "uploaded_count": 100,
  "skipped_count": 0
}
```

### Get Branches

**GET** `/branches`
Get list of branches.

**Response**

```json
{
  "branches": [
    {
      "id": "1",
      "name": "Main Branch",
      "city": "City Name",
      "phone": "1234567890",
      "email": "branch@example.com",
      "created_at": "2023-01-01T12:00:00",
      "is_active": true
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Create Branch

**POST** `/branches`
Create a new branch.

**Request Body**

```json
{
  "name": "New Branch",
  "city": "City Name",
  "phone": "1234567890",
  "email": "branch@example.com"
}
```

**Response**

```json
{
  "branch_id": 2,
  "name": "New Branch",
  "city": "City Name",
  "created_at": "2023-01-01T12:00:00"
}
```

### Get Branch Details

**GET** `/branches/{branch_name}/details`
Get details of a specific branch including users.

**Response**

```json
{
  "branch": {
    "id": "1",
    "name": "Main Branch",
    "city": "City Name",
    "phone": "1234567890",
    "email": "branch@example.com",
    "created_at": "2023-01-01T12:00:00",
    "is_active": true
  },
  "users": {
    "admins": [],
    "drivers": [],
    "total_users": 10
  }
}
```

### Get Admins

**GET** `/admins`
Get list of admins.

**Response**

```json
{
  "admins": [
    {
      "id": "1",
      "name": "Admin User",
      "branch": "Main Branch",
      "email": "admin@example.com",
      "role": "admin",
      "created_at": "2023-01-01T12:00:00",
      "is_active": true
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Create Admin

**POST** `/admins`
Create a new admin.

**Request Body**

```json
{
  "name": "New Admin",
  "email": "admin2@example.com",
  "password": "password123",
  "branch_id": "1"
}
```

**Response**

```json
{
  "admin": {
    "id": "4",
    "name": "New Admin",
    "branch": "Main Branch",
    "email": "admin2@example.com",
    "role": "admin",
    "created_at": "2023-01-01T12:00:00",
    "is_active": true
  },
  "message": "Admin created successfully"
}
```

### Update Admin

**PUT** `/admins/{admin_id}`
Update admin details.

**Request Body**

```json
{
  "name": "Updated Name",
  "email": "updated@example.com",
  "branch_id": "1"
}
```

**Response**

```json
{
  "id": "4",
  "name": "Updated Name",
  "branch": "Main Branch",
  "email": "updated@example.com",
  "role": "admin",
  "created_at": "2023-01-01T12:00:00",
  "is_active": true
}
```

### Update Driver

**PUT** `/drivers/{driver_id}`
Update driver details.

**Request Body**

```json
{
  "driver_name": "Updated Driver",
  "email": "updated_driver@example.com",
  "branch_ids": [1, 2]
}
```

**Response**

```json
{
  "id": "2",
  "username": "updated_driver@example.com",
  "driver_name": "Updated Driver",
  "branches": ["Main Branch", "Second Branch"],
  "role": "driver",
  "isActive": true,
  "isTemporary": false,
  "created_at": "2023-01-01T12:00:00"
}
```

### Delete Driver

**DELETE** `/drivers/{driver_id}`
Delete a driver.

### Delete Admin

**DELETE** `/admins/{admin_id}`
Delete an admin.

### Upload File

**POST** `/files/upload`
Upload a generic file.

**Request Body**
Multipart Form Data: `file`

**Response**

```json
{
  "file_id": "uuid",
  "file_url": "http://...",
  "file_name": "file.txt",
  "file_size": 1024,
  "message": "File uploaded"
}
```

### Get Routes (Admin)

**GET** `/routes`
Get all routes.

**Response**

```json
{
  "routes": [
    {
      "route_number": 1,
      "route_name": "Route A",
      "route_display": "1 - Route A",
      "invoice_count": 10,
      "driver_name": "Driver Name",
      "created_date": "2023-01-01"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Bulk Download PDFs

**POST** `/bulk-download-pdfs`
Download multiple invoice PDFs as a zip.

**Request Body**

```json
{
  "invoice_ids": [1, 2, 3]
}
```

**Response**
Binary file (ZIP)

### Route Wise PDF

**POST** `/route-wise-pdf`
Generate PDF for a specific route.

**Request Body**

```json
{
  "route_name": "Route A",
  "driver_id": 2,
  "date": "2023-01-01",
  "branch_id": 1
}
```

**Response**
Binary file (PDF)

## Driver Operations

### Get Driver Routes

**GET** `/driver-routes`
Get routes assigned to the current driver.

**Response**

```json
{
  "routes": [
    {
      "route_number": 1,
      "route_name": "Route A",
      "route_display": "1 - Route A",
      "invoice_count": 5,
      "driver_name": "Me",
      "created_date": "2023-01-01"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 5
  }
}
```

### Driver Dashboard

**GET** `/dashboard`
Get driver dashboard statistics.

**Response**

```json
{
  "driver_name": "Me",
  "branches": ["Main Branch"],
  "total_invoices": 100,
  "pending_invoices": 20,
  "acknowledged_invoices": 80,
  "today_invoices": 10
}
```

### Get Invoices

**GET** `/invoices`
Get list of invoices for the driver.

**Response**

```json
{
  "invoices": [
    {
      "id": "101",
      "invoice_number": "INV-001",
      "customer_name": "Shop A",
      "amount": 100.0,
      "status": "pending",
      "branch": "Main Branch",
      "created_date": "2023-01-01",
      "is_acknowledged": false
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 5,
    "total_count": 100,
    "per_page": 20
  }
}
```

### Get Invoice Detail

**GET** `/invoices/{invoice_id}`
Get details of a specific invoice.

**Response**

```json
{
  "invoice": {
    "id": "101",
    "invoice_number": "INV-001",
    "customer_name": "Shop A",
    "amount": 100.0,
    "status": "pending",
    "branch": "Main Branch",
    "created_date": "2023-01-01",
    "is_acknowledged": false
  }
}
```

### Acknowledge Invoice

**POST** `/invoices/{invoice_id}/acknowledge`
Acknowledge delivery of an invoice with signature.

**Request Body**

```json
{
  "signature": "base64_encoded_png_string",
  "notes": "Delivered to reception"
}
```

**Response**

```json
{
  "message": "Invoice acknowledged",
  "invoice_id": "101",
  "acknowledged_at": "2023-01-01T13:00:00"
}
```

### Driver Profile

**GET** `/profile`
Get driver profile and statistics.

**Response**

```json
{
  "driver": {
    "id": "2",
    "email": "driver@example.com",
    "name": "Driver Name",
    "role": "driver",
    "branches": ["Main Branch"],
    "is_active": true
  },
  "statistics": {
    "total_invoices": 100,
    "acknowledged_invoices": 80,
    "pending_invoices": 20
  }
}
```

### Download Invoice PDF

**GET** `/invoices/{invoice_id}/download-pdf`
Download invoice PDF.

### Preview Invoice PDF

**GET** `/invoices/{invoice_id}/preview-pdf`
Preview invoice PDF.

### Available Routes

**GET** `/available-routes`
Get available routes for the driver.

**Response**

```json
{
  "routes": [
    {
      "route_number": 1,
      "route_name": "Route A",
      "route_display": "1 - Route A",
      "invoice_count": 5,
      "driver_name": "Me",
      "created_date": "2023-01-01"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Customer Visits

**GET** `/customer-visits`
Get invoices grouped by customer visits.

**Response**

```json
{
  "visits": [
    {
      "customer_name": "Shop A",
      "route_number": 1,
      "route_date": "2023-01-01",
      "invoice_count": 2,
      "total_amount": 200.0,
      "acknowledged_count": 0,
      "is_fully_acknowledged": false,
      "invoice_ids": [101, 102]
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 1,
    "total_count": 1,
    "per_page": 20
  }
}
```

### Customer Visit Detail

**GET** `/customer-visits/{customer_name}/{route_number}/{route_date}`
Get details of a specific customer visit.

**Response**

```json
{
  "customer_name": "Shop A",
  "route_display": "1 - Route A",
  "route_date": "2023-01-01",
  "total_amount": 200.0,
  "acknowledged_count": 0,
  "total_count": 2,
  "invoices": [
    {
      "id": "101",
      "invoice_number": "INV-001",
      "amount": 100.0
    },
    {
      "id": "102",
      "invoice_number": "INV-002",
      "amount": 100.0
    }
  ]
}
```

### Acknowledge Customer Visit

**POST** `/customer-visits/{customer_name}/{route_number}/{route_date}/acknowledge`
Acknowledge all invoices for a customer visit.

**Request Body**

```json
{
  "signature": "base64_encoded_png_string",
  "notes": "Delivered all items"
}
```

**Response**

```json
{
  "message": "Visit acknowledged",
  "customer_name": "Shop A",
  "acknowledged_invoices": ["101", "102"],
  "acknowledged_at": "2023-01-01T13:00:00"
}
```

### Grouped Invoices

**GET** `/invoices-grouped`
Get invoices grouped by customer (optimized view).

**Response**

```json
{
  "groups": [
    {
      "customer_visit_group": "1-Shop A-2023-01-01",
      "customer_name": "Shop A",
      "route_number": 1,
      "invoice_count": 2,
      "total_amount": 200.0,
      "status": "pending",
      "first_invoice_id": 101,
      "invoice_numbers": ["INV-001", "INV-002"],
      "sequence_order": 1
    }
  ],
  "total_groups": 1,
  "pending_groups": 1,
  "delivered_groups": 0
}
```

### Customer Group Detail

**GET** `/customer-group/{group_id}`
Get details of a customer group.

**Response**

```json
{
  "customer_visit_group": "1-Shop A-2023-01-01",
  "customer_name": "Shop A",
  "invoices": [
    {
      "id": "101",
      "invoice_number": "INV-001",
      "amount": 100.0
    }
  ],
  "total_amount": 200.0,
  "invoice_count": 2,
  "all_acknowledged": false
}
```

### Acknowledge Group

**POST** `/acknowledge-group/{group_id}`
Acknowledge a customer group.

**Request Body**

```json
{
  "signature": "base64_encoded_png_string",
  "notes": "Delivered"
}
```

**Response**

```json
{
  "message": "Group acknowledged",
  "customer_name": "Shop A",
  "acknowledged_invoices": ["101", "102"],
  "signature_saved": "path/to/sig.png",
  "pdfs_generated": ["path/to/pdf1.pdf"]
}
```
