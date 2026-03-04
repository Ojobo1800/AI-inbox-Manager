# n8n Phase 1 Notes

Use n8n only as orchestration shell in Phase 1.

Suggested first workflow:
1) Manual Trigger
2) HTTP Request -> GET http://localhost:8000/health
3) IF node checks status == ok
4) Notify success/failure
