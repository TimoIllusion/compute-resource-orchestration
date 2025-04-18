<template>
  <header>
    <nav>
      <div class="logo">GPU Cluster Orchestrator</div>
      <div class="nav-links">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/reservations">Reservations</RouterLink>
      </div>
    </nav>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
header {
  background-color: #2c3e50;
  color: white;
  padding: 0 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-links {
  display: flex;
  gap: 1.5rem;
}

.nav-links a {
  color: #94a3b8;
  text-decoration: none;
  transition: color 0.2s;
}

.nav-links a:hover, 
.nav-links a.router-link-active {
  color: white;
}

main {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
</style>