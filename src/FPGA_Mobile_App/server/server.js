const http = require('http');

let isFalling = false;

const server = http.createServer((request, response) => {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Content-Type', 'application/json');

  if (request.method === 'GET' && request.url === '/status') {
    response.end(JSON.stringify({ isFalling }));
    return;
  }

  if (request.method === 'POST' && request.url === '/simulate-fall') {
    isFalling = true;

    response.end(JSON.stringify({
      success: true,
      signal: 'is_falling',
    }));

    // Reset after five seconds so it can be tested again
    setTimeout(() => {
      isFalling = false;
    }, 5000);

    return;
  }

  response.statusCode = 404;
  response.end(JSON.stringify({ error: 'Not found' }));
});

const port = Number(process.env.PORT || 50222);

server.listen(port, '0.0.0.0', () => {
  console.log(
    `Fall signal server running on port ${port}`
  );
});
