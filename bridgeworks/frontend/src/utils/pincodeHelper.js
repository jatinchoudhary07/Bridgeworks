// Pincode to City Resolution Utility
export const resolveCityFromPincode = (pincode, currentCity) => {
    if (currentCity && currentCity.toString().trim()) return currentCity.toString().trim();
    if (!pincode) return "";
    const pin = pincode.toString().trim();
    if (pin.startsWith('560')) return 'Bengaluru';
    if (pin.startsWith('400')) return 'Mumbai';
    if (pin.startsWith('110')) return 'Delhi';
    if (pin.startsWith('600')) return 'Chennai';
    if (pin.startsWith('700')) return 'Kolkata';
    if (pin.startsWith('500')) return 'Hyderabad';
    if (pin.startsWith('380')) return 'Ahmedabad';
    if (pin.startsWith('226')) return 'Lucknow';
    if (pin.startsWith('411')) return 'Pune';
    if (pin.startsWith('302')) return 'Jaipur';
    if (pin.startsWith('751')) return 'Bhubaneswar';
    if (pin.startsWith('201301') || pin.startsWith('201303')) return 'Noida';
    if (pin.startsWith('122')) return 'Gurugram';
    if (pin.startsWith('800')) return 'Patna';
    if (pin.startsWith('395')) return 'Surat';
    if (pin.startsWith('440')) return 'Nagpur';
    if (pin.startsWith('452')) return 'Indore';
    if (pin.startsWith('141')) return 'Ludhiana';
    if (pin.startsWith('160')) return 'Chandigarh';
    return "";
};
