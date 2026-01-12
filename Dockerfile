# 1. ベースとなるPythonイメージ
FROM python:3.11-slim

# 2. 作業ディレクトリの作成
WORKDIR /app

# 3. 必要なライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. プログラム一式をコピー
COPY ce_receiver.py ce_worker.py ce_utils.py ./

# 5. デフォルトの起動コマンド（Appとして動かす場合）
# ※ Jobとして動かすときは、Code Engine側でこのコマンドを上書きします
CMD ["python", "ce_receiver.py"]
