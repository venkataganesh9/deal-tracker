// frontend/public/script.js
// Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyANOSS11I-0_NRlUQG4VnUt7amBCeqkBkU",
  authDomain: "dealtracker-64cb1.firebaseapp.com",
  projectId: "dealtracker-64cb1",
  storageBucket: "dealtracker-64cb1.firebasestorage.app",
  messagingSenderId: "124984341678",
  appId: "1:124984341678:web:dc88327df62555ee02e93f",
  measurementId: "G-HDPC7EYCKZ"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const db = firebase.firestore();

// DOM elements
const dealGrid = document.getElementById('dealGrid');
const refreshLink = document.getElementById('refreshLink');

// Format currency
function formatCurrency(amount) {
  if (!amount) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount);
}

// Create deal card element
function createDealCard(deal) {
  const card = document.createElement('div');
  card.className = 'deal-card';
  
  card.innerHTML = `
    <div class="deal-image">
      <img src="${deal.image_url || 'https://via.placeholder.com/150'}" alt="${deal.title}">
    </div>
    <div class="deal-content">
      <h3 class="deal-title">${deal.title}</h3>
      <div class="price-container">
        <span class="current-price">${formatCurrency(deal.current_price)}</span>
        ${deal.original_price ? `<span class="original-price">${formatCurrency(deal.original_price)}</span>` : ''}
      </div>
      ${deal.discount_percent > 0 ? `<div class="discount-badge">${deal.discount_percent}% OFF</div>` : ''}
    </div>
    <div class="deal-footer">
      <span class="source">${deal.source}</span>
      <a href="${deal.affiliate_url}" target="_blank" class="deal-button">View Deal</a>
    </div>
  `;
  
  return card;
}

// Load deals in real-time
function loadDeals() {
  dealGrid.innerHTML = '<div class="loading">Loading deals...</div>';
  
  const unsubscribe = db.collection("deals")
    .orderBy("timestamp", "desc")
    .limit(50)
    .onSnapshot(snapshot => {
      // Clear loading state
      dealGrid.innerHTML = '';
      
      if (snapshot.empty) {
        dealGrid.innerHTML = '<div class="loading">No deals available. Check back later!</div>';
        return;
      }
      
      snapshot.forEach(doc => {
        const deal = doc.data();
        const dealCard = createDealCard(deal);
        dealGrid.appendChild(dealCard);
      });
    }, error => {
      console.error("Error loading deals:", error);
      dealGrid.innerHTML = `<div class="loading">Error loading deals: ${error.message}</div>`;
    });
  
  return unsubscribe;
}

// Manual refresh
refreshLink.addEventListener('click', (e) => {
  e.preventDefault();
  loadDeals();
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadDeals();
});