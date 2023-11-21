FROM python:3.11.4-slim-buster
COPY . /app
WORKDIR /app

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install psycopg2-binary
RUN pip install -r requirements.txt

CMD [ "python3", "-m" , "flask", "--app","main","run"]