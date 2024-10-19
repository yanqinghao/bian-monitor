document.addEventListener('DOMContentLoaded', function() {
    const symbolSelect = document.getElementById('symbol');
    const customSymbolInput = document.getElementById('customSymbolInput');

    // Fetch common symbols and populate the select element
    axios.get('/common_symbols')
        .then(response => {
            response.data.forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                option.textContent = symbol;
                symbolSelect.insertBefore(option, symbolSelect.lastElementChild);
            });
        })
        .catch(error => console.error('Error fetching common symbols:', error));

    symbolSelect.addEventListener('change', function() {
        if (this.value === 'custom') {
            customSymbolInput.style.display = 'block';
            customSymbolInput.required = true;
        } else {
            customSymbolInput.style.display = 'none';
            customSymbolInput.required = false;
        }
    });

    document.getElementById('downloadForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const symbol = formData.get('symbol') === 'custom' ? formData.get('customSymbol').toUpperCase() : formData.get('symbol');
        formData.set('symbol', symbol);

        if (formData.get('symbol') === 'custom') {
            formData.delete('customSymbol');
        }

        // Validate the symbol
        try {
            const response = await axios.post('/validate_symbol', formData);
            if (!response.data.valid) {
                alert('Invalid trading pair. Please enter a valid Binance trading pair.');
                return;
            }
        } catch (error) {
            console.error('Error validating symbol:', error);
            alert('An error occurred while validating the trading pair. Please try again.');
            return;
        }

        // Download the data
        try {
            const response = await axios.post('/download', formData, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', response.headers['content-disposition'].split('filename=')[1]);
            document.body.appendChild(link);
            link.click();
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while downloading the data. Please try again.');
        }
    });
});