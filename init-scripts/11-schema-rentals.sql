\c rentals
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE rental (
    id SERIAL PRIMARY KEY,
    rental_uid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    username VARCHAR(80) NOT NULL,
    payment_uid UUID NOT NULL,
    car_uid UUID NOT NULL,
    date_from DATE NOT NULL,
    date_to DATE  NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('IN_PROGRESS', 'FINISHED', 'CANCELED'))
);
