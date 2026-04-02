import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 5000,           // virtual users
  duration: '30s',    // test duration
};

export default function () {
  let res = http.get('http://localhost');

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.1);
}