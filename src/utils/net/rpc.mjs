/* global fetch */
async function update(query) {
  const response = await fetch(
    `${process.env.SUPABASE_URL}/rest/v1/rpc/update_image_url`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: process.env.SUPABASE_KEY,
        Authorization: `Bearer ${process.env.SUPABASE_KEY}`,
      },
      body: JSON.stringify(query),
    },
  );
  const result = await response.json();
  console.log(result);
  return result;
}

export { update };
