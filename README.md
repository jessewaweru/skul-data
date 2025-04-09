# 🏫 Skul Data

A Django-based backend platform designed to help schools in Kenya manage academic records, staff, and student data. This project uses Docker and Docker Compose for seamless setup and environment consistency.

---

## 📁 Project Structure

## 🚀 Getting Started with Docker Compose

1. **Clone the repository:**

```bash

   git clone https://github.com/jessewaweru/skul-data.git

```

2. **Navigate to the project directory:**

```bash

   cd skul_data

```

3. **Ensure Docker and Docker Compose are installed.**

   - Make sure you have the following installed:

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/) (included in Docker Desktop)

4. **Set up your environment variables.**

Copy the .env.example file (you should create this as a template for others) and rename it to .env. In the .env file, fill in the necessary environment variables (like DATABASE_NAME, DATABASE_USER, etc.).

5. **Build and run the project:**

```bash

   docker-compose up --build

```

6. **Access the application:**

   - Open your browser and go to `http://localhost:8000`.

7. **Run migrations (if needed):**

```bash

   docker-compose exec web python manage.py migrate

```

## How This Helps

- **For Developers and Hiring Managers:**
  - Clone the repo, run `docker-compose up`, and everything (including PostgreSQL and your Django app) is set up automatically.
  - No need to install dependencies, configure PostgreSQL, or deal with version issues.

```

```
