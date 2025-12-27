\c payments
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE payment (
    id SERIAL PRIMARY KEY,
    payment_uid UUID NOT NULL DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL CHECK (status IN ('PAID', 'CANCELED')),
    price INT NOT NULL
);
