import styles from "./page.module.css";

export default function AdminHome() {
  return (
    <div className={styles.page}>
      {/* Navbar */}
      <header className={styles.navbar}>
        <div className={styles.logo}>Innovators Admin</div>

        <nav className={styles.navLinks}>
          <a href="#">Dashboard</a>
          <a href="#">Users</a>
          <a href="#">Transactions</a>
          <a href="#" className={styles.loginBtn}>
            Admin Login
          </a>
        </nav>
      </header>

      {/* Hero Section */}
      <main className={styles.hero}>
        {/* Left Side */}
        <div className={styles.left}>
          <span className={styles.badge}>Admin Control Panel</span>

          <h1>
            MANAGE <span>EWALLET</span> SYSTEM
          </h1>

          <p>
            Monitor users, transactions, and platform activities with a secure
            and modern admin dashboard.
          </p>

          <div className={styles.actions}>
            <button className={styles.primaryBtn}>Open Dashboard</button>

            <button className={styles.secondaryBtn}>View Reports</button>
          </div>

          {/* Stats */}
          <div className={styles.stats}>
            <div>
              <h3>25k+</h3>
              <span>Active Users</span>
            </div>

            <div>
              <h3>12M+</h3>
              <span>Transactions</span>
            </div>

            <div>
              <h3>99.99%</h3>
              <span>System Uptime</span>
            </div>
          </div>
        </div>

        {/* Right Side */}
        <div className={styles.right}>
          <div className={styles.card}>
            <div className={styles.cardTop}>
              <span>System Overview</span>
              <span>●</span>
            </div>

            <div className={styles.balance}>
              <p>Total Revenue</p>
              <h2>Rs. 8,45,000</h2>
            </div>

            <div className={styles.transactions}>
              <div className={styles.transaction}>
                <span>New Users Today</span>
                <span className={styles.green}>+ 320</span>
              </div>

              <div className={styles.transaction}>
                <span>Pending Verifications</span>
                <span>18</span>
              </div>

              <div className={styles.transaction}>
                <span>Failed Transactions</span>
                <span className={styles.red}>7</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
