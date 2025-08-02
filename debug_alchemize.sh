#!/bin/bash

echo "🔍 Alchemize Connection Diagnostics"
echo "====================================="

# Test 1: Check if all containers are running
echo -e "\n🐳 Container Status:"
docker-compose ps

# Test 2: Check backend health endpoint
echo -e "\n💓 Backend Health Check:"
echo "Testing http://localhost:8000/health"
curl -s http://localhost:8000/health | jq . || echo "❌ Backend not responding"

# Test 3: Check frontend container environment
echo -e "\n🌐 Frontend Environment Variables:"
docker exec alchemize_frontend printenv | grep API_BASE_URL

# Test 4: Test inter-container communication
echo -e "\n🔗 Inter-container Communication Test:"
echo "Testing from frontend container to backend..."
docker exec alchemize_frontend curl -s http://web:8000/health | jq . || echo "❌ Inter-container communication failed"

# Test 5: Check if Streamlit is running
echo -e "\n📊 Streamlit Process Check:"
docker exec alchemize_frontend ps aux | grep streamlit

# Test 6: Check Streamlit logs
echo -e "\n📝 Recent Streamlit Logs:"
docker logs alchemize_frontend --tail 20

# Test 7: Test API endpoint with auth
echo -e "\n🔐 Testing Auth Endpoint:"
docker exec alchemize_frontend curl -X POST http://web:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@debug.com","password":"testpassword123","full_name":"Debug User"}' \
  -s | jq . || echo "❌ Auth endpoint failed"

# Test 8: Check network connectivity
echo -e "\n🌐 Network Connectivity:"
docker exec alchemize_frontend nslookup web || echo "❌ DNS resolution failed"
docker exec alchemize_frontend ping -c 3 web || echo "❌ Network ping failed"

# Test 9: Check if ports are accessible
echo -e "\n🔌 Port Accessibility:"
docker exec alchemize_frontend nc -zv web 8000 || echo "❌ Port 8000 not accessible"

echo -e "\n✅ Diagnostic complete!"
echo "If you see any ❌ errors above, those are likely the cause of your connection issue."