import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import pkg from 'pg';
import rateLimit from 'express-rate-limit';
import { z } from 'zod';
import jwt from 'jsonwebtoken';
const { Pool } = pkg;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5001;

// Setup PostgreSQL pool
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://dhmc:dhmc_pass@localhost:5432/dhmc_db',
});

// Initialize DB schema
async function initDb() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS sessions (
        id VARCHAR(255) PRIMARY KEY,
        session_id VARCHAR(255),
        scenario_id VARCHAR(255),
        scenario_title VARCHAR(255),
        applicant_name VARCHAR(255),
        loan_amount NUMERIC,
        date TIMESTAMP,
        audit_results JSONB,
        step_records JSONB,
        chain_data JSONB,
        cas_store JSONB
      );
    `);
    console.log('Database schema initialized');
  } catch (err) {
    console.error('Failed to initialize database schema:', err);
  }
}
initDb();

const CORS_ORIGINS = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:5001,http://localhost:3000').split(',');
app.use(cors({ origin: CORS_ORIGINS, credentials: true }));
app.use(express.json({ limit: '10mb' })); // Allow larger payloads for cryptographic data

const JWT_SECRET = process.env.JWT_SECRET || 'super_secret_dhmc_key_change_in_prod';
if (!process.env.JWT_SECRET) {
  console.warn('\x1b[33m[SECURITY WARNING] JWT_SECRET is not set — using insecure default. Set JWT_SECRET in your environment for production.\x1b[0m');
}

// Admin credentials from environment
const ADMIN_USERNAME = process.env.ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin';
if (ADMIN_USERNAME === 'admin' && ADMIN_PASSWORD === 'admin') {
  console.warn('\x1b[33m[SECURITY WARNING] ADMIN_USERNAME and ADMIN_PASSWORD are at insecure defaults (admin/admin). Set them in your environment for production.\x1b[0m');
}

// Rate Limiting
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: { error: 'Too many requests, please try again later.' }
});

app.use('/api/', apiLimiter);

// Auth Middleware
function authenticateToken(req, res, next) {
  // Allow disabling auth locally for easy testing unless strictly enforced
  if (process.env.REQUIRE_AUTH === 'false') return next();

  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) return res.status(401).json({ error: 'Access token missing' });

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.status(403).json({ error: 'Invalid or expired token' });
    req.user = user;
    next();
  });
}

// POST /api/auth/login - Generate JWT for admin access
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body;
  if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
    const token = jwt.sign({ username, role: 'admin' }, JWT_SECRET, { expiresIn: '1h' });
    res.json({ token });
  } else {
    res.status(401).json({ error: 'Invalid credentials' });
  }
});

// Health check
app.get('/api/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', db: 'connected', time: new Date().toISOString() });
  } catch (err) {
    console.error('DB Health Check failed:', err);
    res.status(500).json({ status: 'error', db: 'disconnected' });
  }
});

// GET /api/sessions - Retrieve all sessions metadata
app.get('/api/sessions', async (req, res) => {
  try {
    const result = await pool.query('SELECT id, session_id, date, applicant_name, loan_amount, audit_results, scenario_id, scenario_title FROM sessions ORDER BY date DESC');
    const list = result.rows.map(row => ({
      id: row.id,
      sessionId: row.session_id,
      date: row.date,
      applicantName: row.applicant_name,
      loanAmount: row.loan_amount,
      verdict: row.audit_results?.verdict || 'UNKNOWN',
      scenarioId: row.scenario_id,
      scenarioTitle: row.scenario_title,
    }));
    res.json(list);
  } catch (err) {
    console.error('Error fetching sessions:', err);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});

// GET /api/sessions/:id - Retrieve full session details
app.get('/api/sessions/:id', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM sessions WHERE id = $1', [req.params.id]);
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Session not found' });
    }
    const row = result.rows[0];
    res.json({
      id: row.id,
      sessionId: row.session_id,
      scenarioId: row.scenario_id,
      scenarioTitle: row.scenario_title,
      applicantName: row.applicant_name,
      loanAmount: row.loan_amount,
      date: row.date,
      auditResults: row.audit_results,
      stepRecords: row.step_records,
      chainData: row.chain_data,
      casStore: row.cas_store
    });
  } catch (err) {
    console.error('Error fetching session details:', err);
    res.status(500).json({ error: 'Failed to fetch session' });
  }
});

// Zod validation schema
const SessionSchema = z.object({
  id: z.string().min(1),
  sessionId: z.string().optional(),
  scenarioId: z.string().optional(),
  scenarioTitle: z.string().optional(),
  applicantName: z.string().optional(),
  loanAmount: z.number().optional(),
  auditResults: z.any(),
  stepRecords: z.any().optional(),
  chainData: z.any().optional(),
  casStore: z.any().optional()
});

// POST /api/sessions - Save a new session
app.post('/api/sessions', authenticateToken, async (req, res) => {
  try {
    const validatedData = SessionSchema.parse(req.body);
    const {
      id, sessionId, scenarioId, scenarioTitle, applicantName, loanAmount,
      auditResults, stepRecords, chainData, casStore
    } = validatedData;

    await pool.query(`
      INSERT INTO sessions (id, session_id, scenario_id, scenario_title, applicant_name, loan_amount, date, audit_results, step_records, chain_data, cas_store)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      ON CONFLICT (id) DO UPDATE SET
        session_id = EXCLUDED.session_id,
        scenario_id = EXCLUDED.scenario_id,
        scenario_title = EXCLUDED.scenario_title,
        applicant_name = EXCLUDED.applicant_name,
        loan_amount = EXCLUDED.loan_amount,
        date = EXCLUDED.date,
        audit_results = EXCLUDED.audit_results,
        step_records = EXCLUDED.step_records,
        chain_data = EXCLUDED.chain_data,
        cas_store = EXCLUDED.cas_store
    `, [
      id,
      sessionId || id,
      scenarioId || 'unknown',
      scenarioTitle || 'Custom Scenario',
      applicantName || auditResults?.applicantName || 'Unknown Applicant',
      loanAmount || auditResults?.loanAmount || 0,
      new Date(),
      auditResults,
      stepRecords ? JSON.stringify(stepRecords) : null,
      chainData ? JSON.stringify(chainData) : null,
      casStore ? JSON.stringify(casStore) : null
    ]);

    res.status(201).json({ success: true, session: { id } });
  } catch (err) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: 'Validation failed', details: err.errors });
    }
    console.error('Error saving session:', err);
    res.status(500).json({ error: 'Failed to save session' });
  }
});

// DELETE /api/sessions/:id - Delete a session
app.delete('/api/sessions/:id', authenticateToken, async (req, res) => {
  try {
    // Only admins can delete
    if (req.user && req.user.role !== 'admin') {
      return res.status(403).json({ error: 'Admin privileges required' });
    }
    const result = await pool.query('DELETE FROM sessions WHERE id = $1', [req.params.id]);
    if (result.rowCount === 0) {
      return res.status(404).json({ error: 'Session not found' });
    }
    res.json({ success: true });
  } catch (err) {
    console.error('Error deleting session:', err);
    res.status(500).json({ error: 'Failed to delete session' });
  }
});

// Start Server
app.listen(PORT, () => {
  console.log(`========================================`);
  console.log(`  DHMC Production Backend Running       `);
  console.log(`  URL: http://localhost:${PORT}        `);
  console.log(`  DB Type: PostgreSQL                   `);
  console.log(`========================================`);
});
