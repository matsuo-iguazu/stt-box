import os
import sys
import io
import time
from dotenv import load_dotenv
from ibm_watson import SpeechToTextV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from box_sdk_gen import (
    BoxClient, BoxCCGAuth, CCGConfig, 
    UploadFileAttributes, UploadFileAttributesParentField, UploadFileVersionAttributes
)
# 共通ログを読み込み
from ce_utils import ce_log

load_dotenv()

def get_clients():
    box_config = CCGConfig(
        client_id=os.getenv('BOX_CLIENT_ID'),
        client_secret=os.getenv('BOX_CLIENT_SECRET'),
        enterprise_id=os.getenv('BOX_ENTERPRISE_ID')
    )
    box_client = BoxClient(BoxCCGAuth(box_config))
    stt_auth = IAMAuthenticator(os.getenv('STT_API_KEY'))
    stt = SpeechToTextV1(authenticator=stt_auth)
    stt.set_service_url(os.getenv('STT_SERVICE_URL'))
    return box_client, stt

def find_existing_file(box, folder_id, filename):
    items = box.folders.get_folder_items(folder_id)
    for item in items.entries:
        if item.name == filename:
            return item.id
    return None

def main():
    # 引数の受け取り (Receiverから渡される)
    if len(sys.argv) < 3:
        ce_log("WORKER", "!!! 引数不足", "Usage: ce_worker.py <file_id> <file_name>")
        return
        
    file_id = sys.argv[1]
    file_name = sys.argv[2]

    ce_log("WORKER", "1.処理開始", file_name)
    box, stt = get_clients()
    
    try:
        # 1. ダウンロード
        file_content = box.downloads.download_file(file_id)
        audio_data = io.BytesIO(file_content.read())

        # 2. Watsonジョブ作成
        ce_log("WORKER", "2.ジョブ作成", file_name)
    
        # 拡張子の判定とContent-Typeの決定
        ext = os.path.splitext(file_name)[1].lower()
        if ext == '.mp3':
            content_type = 'audio/mp3'
        elif ext == '.wav':
            content_type = 'audio/wav'
        else:
            # 対応外の拡張子
            ce_log("WORKER", "!!! mp3, wav 以外のファイル", f"{file_name}")
            return  # ここで処理を中断
    
        # 環境変数からモデル名を取得 (デフォルトは ja-JP)
        # ユーザー指定の "ja-JP" をベースにする場合は第2引数を調整してください
        stt_model = os.environ.get('STT_MODEL', 'ja-JP')
    
        # ジョブの作成
        try:
            job = stt.create_job(
                audio=audio_data,
                content_type=content_type,
                model=stt_model,
                results_ttl=1440
            ).get_result()
    
            job_id = job['id']
            ce_log("WORKER", "3.ジョブ監視中", f"Job ID: {job_id} | Model: {stt_model}")
        except Exception as e:
            ce_log("WORKER", "!!! Watsonジョブ作成失敗", str(e))
            return

        # 3. ポーリング
        while True:
            check = stt.check_job(job_id).get_result()
            status = check['status']
            if status == 'completed':
                results = check.get('results', [])
                transcript = "".join([res['alternatives'][0]['transcript'] for res in results[0]['results']]) if results else ""
                break
            elif status in ['failed', 'cancelled']:
                ce_log("WORKER", "!!! エラー終了", f"{file_name} (status: {status})")
                return
            time.sleep(10)

        # 4. テキスト保存
        text_filename = f"{os.path.splitext(file_name)[0]}.txt"
        text_stream = io.BytesIO(transcript.encode('utf-8'))
        text_folder_id = os.getenv('BOX_TEXT_FOLDER_ID')

        existing_id = find_existing_file(box, text_folder_id, text_filename)
        if existing_id:
            box.uploads.upload_file_version(file_id=existing_id, file=text_stream, attributes=UploadFileVersionAttributes(name=text_filename))
        else:
            box.uploads.upload_file(attributes=UploadFileAttributes(name=text_filename, parent=UploadFileAttributesParentField(id=text_folder_id)), file=text_stream)
        
        ce_log("WORKER", "4.テキスト保存", text_filename)

        # 5. ファイル移動
        box.files.update_file_by_id(file_id, parent={"id": os.getenv('BOX_DONE_FOLDER_ID')})
        ce_log("WORKER", "5.ファイル移動", file_name)

        # 6. 処理完了
        ce_log("WORKER", "6.処理完了", file_name)

    except Exception as e:
        ce_log("WORKER", "!!! 異常発生", f"{file_name} ({str(e)})")

if __name__ == '__main__':
    main()
