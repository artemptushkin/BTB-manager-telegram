FROM arm32v7/python:3.8

WORKDIR ./

RUN apt-get update && apt-get install -y rustc

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY . .

CMD [ "python", "-m", "btb_manager_telegram"]
