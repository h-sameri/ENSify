FROM python:3.9
WORKDIR /code
ENV PYTHONPATH "${PYTHONPATH}:/code"
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .
CMD ["bash", "-c", "python /code/main.py & python /code/scheduler.py"]
