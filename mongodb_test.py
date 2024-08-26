from pymongo import MongoClient
from bson import ObjectId

# MongoDB 연결 설정
client = MongoClient('mongodb_connection_string')
db = client['kiteapp']
collection = db['booth']

# 변경하고자 하는 URL 매핑 지정
url_mappings = {
    "old_url_1": "new_url_1",
    "old_url_2": "new_url_2",
    "old_url_3": "new_url_3"
}

def update_urls_in_data(data):
    updates = {}
    stack = [('', data)]
    
    while stack:
        path, value = stack.pop()
        if isinstance(value, dict):
            for k, v in value.items():
                new_path = f"{path}.{k}" if path else k
                if k in ['thumbnail', 'src', 'image'] and isinstance(v, str):
                    new_value = url_mappings.get(v)
                    if new_value:
                        updates[new_path] = new_value
                elif isinstance(v, (dict, list)):
                    stack.append((new_path, v))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                new_path = f"{path}.{i}"
                if isinstance(item, str):
                    new_value = url_mappings.get(item)
                    if new_value:
                        updates[new_path] = new_value
                elif isinstance(item, (dict, list)):
                    stack.append((new_path, item))
    
    return updates

def main():
    document_id = "document_object_id"
    projection = {
        'thumbnail': 1,
        'description.content.attrs.src': 1,
        'product.option.image': 1,
    }

    # MongoDB에서 데이터 가져오기 및 업데이트
    document = collection.find_one({'_id': ObjectId(document_id)}, projection)
    
    if not document:
        print(f"해당하는 문서를 찾을 수 없음: {document_id}")
        return

    updates = update_urls_in_data(document)

    if not updates:
        print("변경사항 없음")
        return

    print("Changes to be made:")
    for key, value in updates.items():
        print(f"{key}: {value}")

    # 변경사항 MongoDB에 적용
    result = collection.update_one(
        {'_id': ObjectId(document_id)},
        {'$set': updates}
    )

    if result.modified_count > 0:
        print(f"업데이트 완료. 변경된 필드: {result.modified_count}")
    else:
        print("변경사항 없음")

    # 업데이트된 문서 재확인
    updated_document = collection.find_one({'_id': ObjectId(document_id)}, projection)
    print("\n업데이트된 문서:")
    print(updated_document)

if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()