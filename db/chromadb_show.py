import chromadb

client = chromadb.PersistentClient(path=r"C:\Analysis_workspace\ad_video_analysis\ad_video_analysis\output\vector_db")
col = client.get_or_create_collection("video_category")

print(f"총 레코드 수: {col.count()}")
data = col.get(include=["documents", "metadatas"])
for rid, meta, doc in zip(data["ids"], data["metadatas"], data["documents"]):
    print(f"\n--- {rid} ---")
    print("meta:", meta)
    print("<doc>")
    print(doc)