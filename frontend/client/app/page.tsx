import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.page}>
      <header className={styles.navbar}>
        <div className={styles.logo}>Innovators Wallet</div>

        <nav className={styles.navLinks}>
          <a href="#">Features</a>
          <a href="#">Security</a>
          <a href="#">Pricing</a>
          <a href="/login" className={styles.loginBtn}>
            Login
          </a>
        </nav>
      </header>

      <main className={styles.hero}>
        <div className={styles.left}>
          <span className={styles.badge}>Modern Digital Payments</span>

          <h1>
            THE <span>INNOVATORS</span> WALLET
          </h1>

          <p>
            Secure, seamless, and ultra-fast payments designed for the next
            generation of digital finance of USA.
          </p>

          <div className={styles.actions}>
            <button className={styles.primaryBtn}>Get Started</button>
            <button className={styles.secondaryBtn}>Learn More</button>
          </div>

          <div className={styles.stats}>
            <div>
              <h3>100k+</h3>
              <span>Users</span>
            </div>

            <div>
              <h3>99.9%</h3>
              <span>Secure</span>
            </div>

            <div>
              <h3>24/7</h3>
              <span>Support</span>
            </div>
          </div>
        </div>

        <div className={styles.right}>
          <div className={styles.card}>
            <div className={styles.cardTop}>
              <span>Innovators Wallet</span>
              <span>●</span>
            </div>

            <div className={styles.balance}>
              <p>Current Balance </p>
              <h2>Rs. 12,480.90</h2>
            </div>

            <div className={styles.transactions}>
              <div className={styles.transaction}>
                <span>Room Rent</span>
                <span>- Rs. 7500</span>
              </div>

              <div className={styles.transaction}>
                <span>Salary</span>
                <span className={styles.green}>+ Rs. 28,281</span>
              </div>

              <div className={styles.transaction}>
                <span>EMI</span>
                <span>- Rs. 1280</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
