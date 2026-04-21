import http from 'k6/z';
import { sleep, check } from 'k6';

// 🔥 Tenants config (realistic)
const tenants = [
  { id: "tenant_1", weight: 50 }, // heavy
  { id: "tenant_2", weight: 30 }, // medium
  { id: "tenant_3", weight: 20 }, // low
];

// 🎯 Weighted random tenant
function pickTenant() {
  const total = tenants.reduce((sum, t) => sum + t.weight, 0);
  let rand = Math.random() * total;

  for (let t of tenants) {
    if (rand < t.weight) return t;
    rand -= t.weight;
  }
}

export const options = {
  scenarios: {
    call_simulation: {
      executor: 'constant-arrival-rate',
      rate: 200, // requests/sec
      timeUnit: '1s',
      duration: '1m',
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
  },
};

export default function () {
  const tenant = pickTenant();

  const headers = {
    'Content-Type': 'application/json',
    'X-Tenant-ID': tenant.id,
  };

  // 1. login
  let loginRes = http.post('http://localhost/login', JSON.stringify({
    email: 'user@test.com',
    password: '123456'
  }), { headers });

  check(loginRes, {
    'login ok': (r) => r.status === 200,
  });

  const token = loginRes.json('token');

  headers['Authorization'] = `Bearer ${token}`;

  // 2. get projects
  let projectRes = http.get('http://localhost/projects', { headers });

  // 3. start call
  let callStart = http.post('http://localhost/call/start', JSON.stringify({
    phone: '123456789'
  }), { headers });

  check(callStart, {
    'call started': (r) => r.status === 200,
  });

  // simulate call duration
  sleep(Math.random() * 2);

  // 4. end call
  http.post('http://localhost/call/end', JSON.stringify({
    call_id: 1
  }), { headers });

  sleep(1);
}